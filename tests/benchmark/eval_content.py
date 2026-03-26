#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""内容层评测：负责计算 C1 与 C2。

这个模块不再关心“调不调工具”或“调哪个工具”，
而是进一步检查：在工具已经大致选对的前提下，参数填得是否准确。

当前指标：
- C1 Parameter Exact Match：参数整体是否完全一致
- C2 Parameter Field Accuracy：按字段计算命中率，再求平均

依赖：
- 项目内 schema：`BenchmarkCase`
- 项目内工具函数：`all_tool_calls`、`parse_tool_arguments`、`safe_mean`

是否可单独运行：
- 不能直接作为 CLI 独立运行
- 是 benchmark 主流程中的一个评分子模块
- 可以在测试中单独调用

输入：
- 单条 `BenchmarkCase`
- 对应的一条标准化 trace

输出：
- `{"C1": float, "C2": float}`

评分原则：
- C1 更严格，要求整组参数完全一致
- C2 更细粒度，允许部分字段正确
- 当前 MVP 版本按工具名取第一条匹配调用进行比较，保持规则简单稳定
"""

from __future__ import annotations

from typing import Any

from tests.benchmark.benchmark_schema import BenchmarkCase
from tests.benchmark.benchmark_utils import all_tool_calls, parse_tool_arguments, safe_mean


def evaluate_content_case(
    case: BenchmarkCase,
    trace: list[dict[str, Any]],
) -> dict[str, float]:
    """对单条 trace 计算 C1/C2 内容指标。"""
    if case.expected_behavior != "tool_call":
        return {"C1": 0.0, "C2": 0.0}

    actual_by_tool: dict[str, list[dict[str, Any]]] = {}
    for call in all_tool_calls(trace):
        function = call.get("function", {})
        name = function.get("name")
        if not isinstance(name, str):
            continue
        actual_by_tool.setdefault(name, []).append(parse_tool_arguments(function.get("arguments", {})))

    exact_matches: list[float] = []
    field_scores: list[float] = []
    # MVP 版本先按工具名匹配到第一条调用，保持评分逻辑简单稳定。
    for tool_name, expected_args in case.expected_tool_args.items():
        candidates = actual_by_tool.get(tool_name, [])
        actual_args = candidates[0] if candidates else {}
        exact_matches.append(1.0 if actual_args == expected_args else 0.0)

        if not expected_args:
            continue
        matched_fields = sum(
            1 for key, value in expected_args.items() if actual_args.get(key) == value
        )
        field_scores.append(matched_fields / len(expected_args))

    return {
        "C1": safe_mean(exact_matches),
        "C2": safe_mean(field_scores),
    }
