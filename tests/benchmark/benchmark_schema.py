#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""定义 benchmark 的基础数据结构与样本加载逻辑。

这个模块是整个 benchmark 的数据入口，负责两件事：
- 定义统一的 `BenchmarkCase` 数据结构
- 把 JSON 文件中的 case 加载成代码里可直接使用的对象

依赖：
- Python 标准库：`dataclasses`、`json`、`pathlib`

是否可单独运行：
- 不能作为命令行脚本独立运行
- 它是 `run_benchmark.py`、各个 `eval_*.py`、以及测试文件的底层依赖模块

输入：
- benchmark case JSON 文件

输出：
- `BenchmarkCase` 对象列表

设计作用：
- 统一不同数据文件的字段格式
- 为后续 runner 和 evaluator 提供稳定接口
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class BenchmarkCase:
    """benchmark case 的类型化定义，供 runner 与 evaluator 共用。"""

    id: str
    case_type: str
    user_input: str
    context: dict[str, Any] = field(default_factory=dict)
    expected_behavior: str = "tool_call"
    expected_tools: list[str] = field(default_factory=list)
    expected_tool_args: dict[str, dict[str, Any]] = field(default_factory=dict)
    expected_sequence: list[str] = field(default_factory=list)
    expected_parallel_groups: list[list[str]] = field(default_factory=list)
    required_missing_slots: list[str] = field(default_factory=list)
    rejection_category: str | None = None
    notes: str = ""


def load_cases(path: str | Path) -> list[BenchmarkCase]:
    """将 JSON 数组格式的样本文件加载成 BenchmarkCase 列表。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Benchmark case file must contain a JSON array")
    return [BenchmarkCase(**item) for item in payload]
