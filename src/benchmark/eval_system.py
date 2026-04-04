#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""系统层评测：负责计算 S1 到 S5。

这一层不再只看单个工具调用，而是评估完整 trace 是否体现出 Agent 的系统能力。

当前指标：
- S1 Sequential Tool Call Accuracy：顺序调用是否符合依赖顺序
- S2 Parallel Tool Call Accuracy：应并行的工具是否在同一 assistant turn 中共同出现
- S3 Rejection Rate：越界请求是否正确拒绝
- S4 Clarification Rate：信息不足时是否正确追问
- S5 End-to-End Task Success：整条任务链是否成功完成

依赖：
- 项目内 schema：`BenchmarkCase`
- 项目内公共工具：trace 提取、行为识别、终态消息提取
- 项目内低层评测：`evaluate_routing_case`、`evaluate_content_case`

是否可单独运行：
- 不能作为独立 CLI 运行
- 是 benchmark 主 runner 在系统层打分时调用的模块
- 可以被测试文件单独 import 验证规则

输入：
- 单条 `BenchmarkCase`
- 对应的一条标准化 trace

输出：
- `{"S1": float, "S2": float, "S3": float, "S4": float, "S5": float}`

评分原则概览：
- S1：比较实际工具序列与 `expected_sequence`
- S2：判断预期并行工具是否出现在同一 assistant 消息内
- S3：要求行为类型是拒答，且没有误调业务工具
- S4：要求行为类型是澄清，且覆盖关键缺失槽位
- S5：把行为类别、工具调用、参数质量、顺序/并行约束、最终完成态综合成规则化成功信号

说明：
- 这套规则刻意保持确定性，不依赖人工主观判断
- 第一版 S2 判定的是“同轮成组出现”，不是运行时真的异步并发
"""

from __future__ import annotations

from typing import Any

from src.benchmark.benchmark_schema import BenchmarkCase
from src.benchmark.benchmark_utils import (
    all_tool_calls,
    assistant_messages,
    final_assistant_message,
    infer_behavior,
)
from src.benchmark.eval_content import evaluate_content_case
from src.benchmark.eval_routing import evaluate_routing_case
from src.benchmark.benchmark_utils import parse_tool_arguments


SLOT_ALIASES = {
    "budget": ["budget", "预算", "花费", "投放金额"],
    "target_audience": ["target_audience", "目标受众", "受众", "目标用户", "人群"],
    "platform": ["platform", "平台", "投放平台"],
    "campaign_id": ["campaign_id", "活动id", "campaign", "活动编号"],
    "file_path": ["file_path", "文件", "素材文件", "视频", "图片", "路径"],
    "app_id": ["app_id", "app", "应用", "应用id", "应用ID"],
    "competitor_name": ["competitor_name", "competitor", "竞品", "竞品名称"],
    "game_genre": ["game_genre", "genre", "品类", "游戏品类", "类型"],
}


def evaluate_system_case(case, trace):
    behavior = infer_behavior(trace)
    routing = evaluate_routing_case(case, trace)
    content = evaluate_content_case(case, trace)

    scores = {}

    if case.case_type == "sequential":
        scores["S1"] = _sequential_score(case, trace)
    if case.case_type == "parallel":
        scores["S2"] = _parallel_score(case, trace)
    if case.expected_behavior == "reject":
        scores["S3"] = 1.0 if behavior == "reject" else 0.0
    if case.expected_behavior == "clarify":
        scores["S4"] = _clarify_score(case, trace)

    scores["S5"] = _task_success(case, trace, behavior, routing, content,
                                  scores.get("S1", 0.0), scores.get("S2", 0.0),
                                  scores.get("S3", 0.0), scores.get("S4", 0.0))
    return scores


def _sequential_score(case: BenchmarkCase, trace: list[dict[str, Any]]) -> float:
    """检查顺序调用样本是否严格遵循 gold 工具顺序。"""
    if case.case_type != "sequential":
        return 0.0
    assistant_with_tools = [
        message for message in assistant_messages(trace) if message.get("tool_calls")
    ]
    predicted_sequence = []
    for message in assistant_with_tools:
        for call in message.get("tool_calls", []):
            predicted_sequence.append(call.get("function", {}).get("name"))
    return 1.0 if predicted_sequence == case.expected_sequence else 0.0


def _parallel_score(case: BenchmarkCase, trace: list[dict[str, Any]]) -> float:
    """检查并行工具是否在同一条 assistant 消息中共同出现。"""
    if case.case_type != "parallel":
        return 0.0
    expected_groups = case.expected_parallel_groups
    if not expected_groups:
        return 0.0

    assistant_with_tools = [
        message for message in assistant_messages(trace) if message.get("tool_calls")
    ]
    predicted_groups: list[list[str]] = []
    for message in assistant_with_tools:
        predicted_groups.append(
            [call.get("function", {}).get("name") for call in message.get("tool_calls", [])]
        )

    normalized_expected = [sorted(group) for group in expected_groups]
    for group, message in zip(normalized_predicted := predicted_groups, assistant_with_tools):
        if sorted(group) not in normalized_expected:
            continue
        if _parallel_args_match(case, message.get("tool_calls", [])):
            return 1.0
    return 0.0


def _parallel_args_match(case: BenchmarkCase, tool_calls: list[dict[str, Any]]) -> bool:
    if not case.expected_tool_args:
        return True

    actual_by_tool: dict[str, list[dict[str, Any]]] = {}
    for call in tool_calls:
        function = call.get("function", {})
        name = function.get("name")
        if not isinstance(name, str):
            continue
        actual_by_tool.setdefault(name, []).append(parse_tool_arguments(function.get("arguments", {})))

    for tool_name, expected_args in case.expected_tool_args.items():
        candidates = list(actual_by_tool.get(tool_name, []))
        if isinstance(expected_args, list):
            if len(candidates) < len(expected_args):
                return False
            remaining = list(candidates)
            for expected_item in expected_args:
                match_index = next(
                    (
                        index for index, candidate in enumerate(remaining)
                        if all(candidate.get(key) == value for key, value in expected_item.items())
                    ),
                    None,
                )
                if match_index is None:
                    return False
                remaining.pop(match_index)
        else:
            if not any(
                all(candidate.get(key) == value for key, value in expected_args.items())
                for candidate in candidates
            ):
                return False
    return True


def _clarify_score(case: BenchmarkCase, trace: list[dict[str, Any]]) -> float:
    """检查澄清回复是否覆盖要求追问的关键缺失槽位。"""
    if case.expected_behavior != "clarify":
        return 0.0
    if infer_behavior(trace) != "clarify":
        return 0.0
    first_message = assistant_messages(trace)[0] if assistant_messages(trace) else None
    content = str(first_message.get("content", "")) if first_message else ""
    if not case.required_missing_slots:
        return 1.0
    matched = 0
    lowered = content.lower()
    # 允许少量同义表达，避免 benchmark 对具体措辞过于脆弱。
    for slot in case.required_missing_slots:
        aliases = SLOT_ALIASES.get(slot, [slot])
        if any(alias in content or alias.lower() in lowered for alias in aliases):
            matched += 1
    return matched / len(case.required_missing_slots)


def _task_success(
    case: BenchmarkCase,
    trace: list[dict[str, Any]],
    behavior: str,
    routing: dict[str, float],
    content: dict[str, float],
    s1: float,
    s2: float,
    s3: float,
    s4: float,
) -> float:
    """把底层判断折叠成确定性的端到端成功信号。"""
    final_message = final_assistant_message(trace)
    has_terminal_answer = final_message is not None and bool(str(final_message.get("content", "")).strip())

    if case.expected_behavior == "reject":
        return 1.0 if s3 == 1.0 and not all_tool_calls(trace) else 0.0
    if case.expected_behavior == "clarify":
        return 1.0 if s4 == 1.0 and not all_tool_calls(trace) else 0.0
    if case.case_type == "sequential":
        return 1.0 if routing.get("R1", 0.0) and s1 and has_terminal_answer else 0.0
    if case.case_type == "parallel":
        return 1.0 if routing.get("R1", 0.0) and s2 and has_terminal_answer else 0.0
    return 1.0 if (behavior == "tool_call" 
               and routing.get("R2", 0.0) 
               and content.get("C2", 0.0) == 1.0 
               and has_terminal_answer) else 0.0
