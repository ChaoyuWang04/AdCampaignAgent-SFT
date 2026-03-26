#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试 benchmark case 的加载逻辑。

这个测试文件只负责验证 `benchmark_schema.py` 中的样本读取能力是否正常，
确保 JSON 文件能够被解析为统一的 `BenchmarkCase` 对象。

依赖：
- Python 标准库：`json`、`pathlib`
- 项目内模块：`tests.benchmark.benchmark_schema`

是否可单独运行：
- 可以通过 `pytest tests/benchmark/test_benchmark_schema.py` 单独运行
- 不能作为生产脚本独立承担 benchmark 执行任务，它只是测试模块

输入：
- 临时构造的 benchmark JSON 文件

输出：
- 无文件输出
- 通过 pytest 断言验证加载结果
"""

import json
from pathlib import Path

from tests.benchmark.benchmark_schema import BenchmarkCase, load_cases


def test_load_cases_parses_expected_schema(tmp_path: Path) -> None:
    """合法的 case 文件应该被正确加载成 BenchmarkCase。"""
    payload = [
        {
            "id": "std_001",
            "case_type": "standard",
            "user_input": "帮我看一下 CMP_2048 最近 7 天的表现",
            "context": {"platform": "Meta", "campaign_id": "CMP_2048"},
            "expected_behavior": "tool_call",
            "expected_tools": ["get_campaign_metrics"],
            "expected_tool_args": {
                "get_campaign_metrics": {
                    "campaign_id": "CMP_2048",
                    "date_range": "last_7_days",
                }
            },
        }
    ]
    case_file = tmp_path / "cases.json"
    case_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    cases = load_cases(case_file)

    assert len(cases) == 1
    case = cases[0]
    assert isinstance(case, BenchmarkCase)
    assert case.id == "std_001"
    assert case.expected_tools == ["get_campaign_metrics"]
    assert case.expected_tool_args["get_campaign_metrics"]["campaign_id"] == "CMP_2048"
