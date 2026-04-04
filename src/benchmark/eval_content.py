#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""内容层评测：负责计算 C1 与 C2。

这个模块不再关心“调不调工具”或“调哪个工具”，
而是进一步检查：在工具已经大致选对的前提下，参数填得是否准确。

当前指标：
- C1 Parameter Gold Coverage：gold 参数是否被完整覆盖
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
- C1 更严格，要求 gold 参数集合被完整覆盖
- C2 更细粒度，允许部分字段正确
- 当前 MVP 版本按工具名取第一条匹配调用进行比较，保持规则简单稳定
"""

from __future__ import annotations

from typing import Any

from src.benchmark.benchmark_schema import BenchmarkCase
from src.benchmark.benchmark_utils import all_tool_calls, parse_tool_arguments, safe_mean


def _field_accuracy(actual_args: dict[str, Any], expected_args: dict[str, Any]) -> float:
    if not expected_args:
        return 1.0
    matched_fields = sum(
        1 for key, value in expected_args.items() if actual_args.get(key) == value
    )
    return matched_fields / len(expected_args)


def _score_expected_args(
    candidates: list[dict[str, Any]],
    expected_args: dict[str, Any] | list[dict[str, Any]],
) -> tuple[list[float], list[float]]:
    if isinstance(expected_args, list):
        remaining = list(candidates)
        exact_matches: list[float] = []
        field_scores: list[float] = []
        for expected_item in expected_args:
            if not remaining:
                exact_matches.append(0.0)
                field_scores.append(0.0)
                continue
            ranked = [
                (
                    1.0 if all(candidate.get(key) == value for key, value in expected_item.items()) else 0.0,
                    _field_accuracy(candidate, expected_item),
                    index,
                )
                for index, candidate in enumerate(remaining)
            ]
            exact_score, field_score, picked_index = max(ranked, key=lambda item: (item[0], item[1]))
            exact_matches.append(exact_score)
            field_scores.append(field_score)
            remaining.pop(picked_index)
        return exact_matches, field_scores

    actual_args = candidates[0] if candidates else {}
    exact_match = (
        1.0
        if all(actual_args.get(key) == value for key, value in expected_args.items())
        else 0.0
    )
    return [exact_match], [_field_accuracy(actual_args, expected_args)]


def evaluate_content_case(
    case: BenchmarkCase,
    trace: list[dict[str, Any]],
) -> dict[str, float]:
    """对单条 trace 计算 C1/C2 内容指标。"""
    if case.expected_behavior != "tool_call":
        return {}

    actual_by_tool: dict[str, list[dict[str, Any]]] = {}
    for call in all_tool_calls(trace):
        function = call.get("function", {})
        name = function.get("name")
        if not isinstance(name, str):
            continue
        actual_by_tool.setdefault(name, []).append(parse_tool_arguments(function.get("arguments", {})))

    exact_matches: list[float] = []
    field_scores: list[float] = []
    for tool_name, expected_args in case.expected_tool_args.items():
        candidates = actual_by_tool.get(tool_name, [])
        tool_exact_matches, tool_field_scores = _score_expected_args(candidates, expected_args)
        exact_matches.extend(tool_exact_matches)
        field_scores.extend(tool_field_scores)

    if not exact_matches:
        return {}

    return {
        "C1": safe_mean(exact_matches),
        "C2": safe_mean(field_scores) if field_scores else safe_mean(exact_matches),
    }
