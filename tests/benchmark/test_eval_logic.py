#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试 benchmark 各层评分逻辑。

这个测试文件验证四类 evaluator 的最小正确性：
- 格式层：F1、F2
- 路由层：R1、R2、R3
- 内容层：C1、C2
- 系统层：S1、S2、S3、S4、S5

依赖：
- 项目内 schema：`tests.benchmark.benchmark_schema`
- 项目内评分器：`tests.benchmark.eval_*`

是否可单独运行：
- 可以通过 `pytest tests/benchmark/test_eval_logic.py` 单独运行
- 不能独立执行真实模型，只是用构造好的 trace 验证评分规则

输入：
- 测试内部手工构造的 `BenchmarkCase`
- 测试内部手工构造的标准化 trace

输出：
- 无文件输出
- 通过 pytest 断言验证各指标分数是否符合预期
"""

from tests.benchmark.benchmark_schema import BenchmarkCase
from tests.benchmark.eval_content import evaluate_content_case
from tests.benchmark.eval_format import evaluate_format_case
from tests.benchmark.eval_routing import evaluate_routing_case
from tests.benchmark.eval_system import evaluate_system_case


def test_standard_case_scores_format_routing_and_content() -> None:
    """标准正确 trace 应该在基础指标上拿到满分。"""
    case = BenchmarkCase(
        id="std_001",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天的表现",
        context={},
        expected_behavior="tool_call",
        expected_tools=["get_campaign_metrics"],
        expected_tool_args={
            "get_campaign_metrics": {
                "campaign_id": "CMP_2048",
                "date_range": "last_7_days",
            }
        },
    )
    trace = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_campaign_metrics",
                        "arguments": (
                            '{"campaign_id":"CMP_2048","date_range":"last_7_days"}'
                        ),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"ok": true}'},
        {"role": "assistant", "content": "最近 7 天表现稳定。"},
    ]

    format_result = evaluate_format_case(case, trace)
    routing_result = evaluate_routing_case(case, trace)
    content_result = evaluate_content_case(case, trace)
    system_result = evaluate_system_case(case, trace)

    assert format_result["F1"] == 1.0
    assert format_result["F2"] == 1.0
    assert routing_result["R1"] == 1.0
    assert routing_result["R2"] == 1.0
    assert routing_result["R3"] == 1.0
    assert content_result["C1"] == 1.0
    assert content_result["C2"] == 1.0
    assert system_result["S5"] == 1.0


def test_reject_and_clarify_cases_are_distinguished() -> None:
    """拒答和澄清 trace 应该被判成不同的路由与系统结果。"""
    reject_case = BenchmarkCase(
        id="oos_001",
        case_type="oos",
        user_input="帮我登录竞争对手账户",
        context={},
        expected_behavior="reject",
    )
    clarify_case = BenchmarkCase(
        id="clarify_001",
        case_type="clarify",
        user_input="帮我创建一个广告活动",
        context={},
        expected_behavior="clarify",
        required_missing_slots=["budget", "target_audience"],
    )

    reject_trace = [
        {"role": "assistant", "content": "抱歉，这个请求超出权限范围，我不能帮助执行。"}
    ]
    clarify_trace = [
        {"role": "assistant", "content": "请先告诉我预算和目标受众，我再帮你创建活动。"}
    ]

    reject_routing = evaluate_routing_case(reject_case, reject_trace)
    reject_system = evaluate_system_case(reject_case, reject_trace)
    clarify_routing = evaluate_routing_case(clarify_case, clarify_trace)
    clarify_system = evaluate_system_case(clarify_case, clarify_trace)

    assert reject_routing["R1"] == 1.0
    assert reject_system["S3"] == 1.0
    assert clarify_routing["R1"] == 1.0
    assert clarify_system["S4"] == 1.0


def test_sequential_and_parallel_system_scores() -> None:
    """顺序和并行 trace 应该分别满足对应的系统指标。"""
    sequential_case = BenchmarkCase(
        id="seq_001",
        case_type="sequential",
        user_input="先分析上周表现，再给我优化建议",
        context={},
        expected_behavior="tool_call",
        expected_tools=["get_campaign_metrics", "get_optimization_playbook"],
        expected_sequence=["get_campaign_metrics", "get_optimization_playbook"],
    )
    parallel_case = BenchmarkCase(
        id="par_001",
        case_type="parallel",
        user_input="同时查 iOS 和 Android 的报告",
        context={},
        expected_behavior="tool_call",
        expected_tools=["get_campaign_metrics", "get_campaign_metrics"],
        expected_parallel_groups=[["get_campaign_metrics", "get_campaign_metrics"]],
    )

    sequential_trace = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_campaign_metrics",
                        "arguments": '{"campaign_id":"CMP_2048"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"roas_d7": 0.81}'},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "get_optimization_playbook",
                        "arguments": '{"issue":"roas_drop"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_2", "content": '{"action": "tighten bids"}'},
        {"role": "assistant", "content": "建议先收紧出价。"},
    ]
    parallel_trace = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_campaign_metrics",
                        "arguments": '{"platform":"iOS"}',
                    },
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "get_campaign_metrics",
                        "arguments": '{"platform":"Android"}',
                    },
                },
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": '{"platform":"iOS"}'},
        {"role": "tool", "tool_call_id": "call_2", "content": '{"platform":"Android"}'},
        {"role": "assistant", "content": "两个平台数据都查到了。"},
    ]

    sequential_system = evaluate_system_case(sequential_case, sequential_trace)
    parallel_system = evaluate_system_case(parallel_case, parallel_trace)

    assert sequential_system["S1"] == 1.0
    assert sequential_system["S5"] == 1.0
    assert parallel_system["S2"] == 1.0
    assert parallel_system["S5"] == 1.0
