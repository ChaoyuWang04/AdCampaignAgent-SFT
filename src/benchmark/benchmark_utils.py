#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""提供 benchmark 通用辅助函数。

这个模块不直接执行 benchmark，也不直接打分，而是负责提供多个子模块都会用到的基础能力：
- 结果目录创建
- tool call 参数解析
- trace 中 assistant/tool call 的提取
- 高层行为类型推断
- 多工具集合 F1 计算
- 指标均值聚合

依赖：
- Python 标准库：`json`、`collections`、`pathlib`

是否可单独运行：
- 不能独立运行
- 它是 `benchmark_runner.py` 与各个 `eval_*.py` 的公共依赖模块

输入：
- 标准化 trace
- 工具参数字符串或 dict
- 指标分数列表

输出：
- 解析后的结构化数据
- 行为类别
- 聚合后的基础分数

说明：
- 这里的行为识别使用确定性的规则，而不是模型或语义判断
- 这样做的目的是让 benchmark 在不同时间重复执行时保持一致
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REJECTION_SIGNAL_GROUPS = [
    [
        "权限范围",
        "超出我的权限",
        "超出了我的权限",
        "无权",
        "越权",
        "高风险操作",
        "不被允许",
    ],
    [
        "服务范围",
        "能力范围",
        "超出我的服务范围",
        "超出了我的服务范围",
        "超出我的能力范围",
        "超出了我的能力范围",
        "不属于我处理范围",
    ],
    [
        "无法执行",
        "不能执行",
        "无法帮助",
        "无法处理",
        "不能帮你",
        "拒绝",
    ],
    [
        "请通过平台后台",
        "联系账户经理",
        "联系管理员",
        "联系您的账户经理",
        "请走平台后台",
    ],
]


def ensure_results_dir(path: str | Path) -> Path:
    """确保 benchmark 结果目录存在，不存在时自动创建。"""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def parse_tool_arguments(raw_arguments: str | dict[str, Any]) -> dict[str, Any]:
    """将 tool call 参数统一解析成 dict，便于后续打分。"""
    if isinstance(raw_arguments, dict):
        return raw_arguments
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def assistant_messages(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从标准化 trace 中筛出所有 assistant 消息。"""
    return [message for message in trace if message.get("role") == "assistant"]


def all_tool_calls(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把多个 assistant turn 中的 tool call 展平成一个列表。"""
    calls: list[dict[str, Any]] = []
    for message in assistant_messages(trace):
        for call in message.get("tool_calls", []):
            if isinstance(call, dict):
                calls.append(call)
    return calls


def called_tool_names(trace: list[dict[str, Any]]) -> list[str]:
    """按出现顺序提取 trace 中所有工具名。"""
    names: list[str] = []
    for call in all_tool_calls(trace):
        function = call.get("function", {})
        name = function.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def infer_behavior(trace: list[dict[str, Any]]) -> str:
    """根据完整 trace 推断高层行为类型。"""
    if all_tool_calls(trace):
        return "tool_call"

    assistant_content = " ".join(
        str(message.get("content", "")) for message in assistant_messages(trace)
    )
    clarify_signals = [
        "请问您",
        "请提供",
        "告诉我",
        "方便告知",
        "缺少",
        "能否提供",
        "需要知道",
        "哪个campaign",
        "哪个平台",
        "哪个app",
    ]

    rejection_group_hits = sum(
        1
        for group in REJECTION_SIGNAL_GROUPS
        if any(token in assistant_content for token in group)
    )
    has_reject = rejection_group_hits >= 1
    has_clarify = any(token in assistant_content for token in clarify_signals)

    # 拒答优先于追问，避免“请告知...但此操作超出权限”被误判成 clarify。
    if has_reject:
        return "reject"
    if has_clarify:
        return "clarify"
    return "direct_answer"


def final_assistant_message(trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    """返回最后一条 assistant 消息，作为任务终态判断依据。"""
    messages = assistant_messages(trace)
    return messages[-1] if messages else None


def multiset_f1(predicted: list[str], expected: list[str]) -> float:
    """计算 multiset F1，使并行场景中的重复工具也能被正确计数。"""
    predicted_counter = Counter(predicted)
    expected_counter = Counter(expected)
    overlap = sum((predicted_counter & expected_counter).values())
    if not predicted and not expected:
        return 1.0
    if not predicted or not expected:
        return 0.0
    precision = overlap / len(predicted)
    recall = overlap / len(expected)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def safe_mean(values: list[float]) -> float:
    """对指标列表求平均；空列表时返回 0，避免异常。"""
    if not values:
        return 0.0
    return sum(values) / len(values)
