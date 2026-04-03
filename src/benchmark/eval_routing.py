#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""路由层评测：负责计算 R1、R2、R3。

这个模块回答的是“模型是否做出了正确的动作决策”：
- 是该调工具，还是该拒答，还是该追问
- 如果要调工具，工具是否选对
- 如果一次涉及多个工具，工具集合是否接近 gold

当前指标：
- R1：行为决策准确率
- R2：单工具或顺序工具选择是否完全匹配
- R3：多工具集合 F1

依赖：
- 项目内 schema：`BenchmarkCase`
- 项目内工具函数：`infer_behavior`、`called_tool_names`、`multiset_f1`

是否可单独运行：
- 不能直接命令行运行
- 是 `benchmark_runner.py` 聚合评测时依赖的子模块
- 可以在测试或 notebook 中单独 import 使用

输入：
- 单条 `BenchmarkCase`
- 对应的一条标准化 trace

输出：
- `{"R1": float, "R2": float, "R3": float}`

评分原则：
- R1 比较 trace 推断出的行为类别与 `expected_behavior`
- R2 要求工具顺序完全一致
- R3 用 F1 处理多工具情况，适合并行或集合式调用
"""

from __future__ import annotations

from typing import Any

from src.benchmark.benchmark_schema import BenchmarkCase
from src.benchmark.benchmark_utils import called_tool_names, infer_behavior, multiset_f1


def evaluate_routing_case(
    case: BenchmarkCase,
    trace: list[dict[str, Any]],
) -> dict[str, float]:
    """对单条 trace 计算 R1/R2/R3 路由指标。"""
    predicted_behavior = infer_behavior(trace)
    predicted_tools = called_tool_names(trace)

    r1 = 1.0 if predicted_behavior == case.expected_behavior else 0.0

    # 非工具调用类样本只参与顶层行为决策准确率，不参与工具选择评分。
    if case.expected_behavior != "tool_call":
        return {"R1": r1}

    expected_tools = case.expected_tools
    r2 = 1.0 if predicted_tools == expected_tools else 0.0
    r3 = multiset_f1(predicted_tools, expected_tools)
    return {"R1": r1, "R2": r2, "R3": r3}
