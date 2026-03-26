#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""格式层评测：负责计算 F1 与 F2。

这个模块只关注“模型输出的工具调用格式是否可被系统接住”，
不判断工具选得对不对，也不判断参数语义是否正确。

当前指标：
- F1 Parsability：trace 中是否存在可解析的 tool call
- F2 Format Compliance：tool call 是否满足最基本的结构要求，例如：
  - 有工具名
  - 参数可以被解析为字典

依赖：
- 项目内 schema：`BenchmarkCase`
- 项目内工具函数：`all_tool_calls`、`parse_tool_arguments`

是否可单独运行：
- 不能作为命令行脚本独立运行
- 它由 `benchmark_runner.py` 在整套 benchmark 流程中调用
- 也可以在测试中被单独 import 调用

输入：
- 单条 `BenchmarkCase`
- 对应的一条标准化 trace

输出：
- `{"F1": float, "F2": float}`

评分原则：
- 当前是规则化判定，不依赖人工
- 如果 trace 中根本没有 tool call，则 F1/F2 都为 0
- 如果有 tool call 但结构残缺，则 F2 为 0
"""

from __future__ import annotations

from typing import Any

from tests.benchmark.benchmark_schema import BenchmarkCase
from tests.benchmark.benchmark_utils import all_tool_calls, parse_tool_arguments


def evaluate_format_case(
    case: BenchmarkCase,
    trace: list[dict[str, Any]],
) -> dict[str, float]:
    """对单条 trace 计算 F1/F2 格式指标。"""
    _ = case
    tool_calls = all_tool_calls(trace)
    if not tool_calls:
        return {"F1": 0.0, "F2": 0.0}

    parseable = 1.0
    compliant = 1.0
    for call in tool_calls:
        function = call.get("function", {})
        if not isinstance(function.get("name"), str):
            parseable = 0.0
            compliant = 0.0
            break
        arguments = parse_tool_arguments(function.get("arguments", {}))
        if not isinstance(arguments, dict):
            compliant = 0.0
            break
    return {"F1": parseable, "F2": compliant}
