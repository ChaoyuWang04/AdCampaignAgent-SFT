from src.benchmark.benchmark_schema import BenchmarkCase
from src.benchmark.eval_system import evaluate_system_case


def test_clarify_score_accepts_app_id_alias_in_chinese_prompt() -> None:
    case = BenchmarkCase(
        id="clarify_app_id",
        case_type="clarify",
        user_input="帮我分析一下这个应用的留存。",
        expected_behavior="clarify",
        required_missing_slots=["app_id"],
    )
    trace = [
        {"role": "assistant", "content": "为了继续分析，请提供应用ID。"},
    ]

    scores = evaluate_system_case(case, trace)

    assert scores["S4"] == 1.0
    assert scores["S5"] == 1.0


def test_parallel_score_rejects_duplicate_same_tool_when_expected_subtasks_differ() -> None:
    case = BenchmarkCase(
        id="par_policy_types",
        case_type="parallel",
        user_input="同时帮我查 Meta 的广告格式政策和内容限制政策。",
        expected_behavior="tool_call",
        expected_tools=["get_platform_policy", "get_platform_policy"],
        expected_parallel_groups=[["get_platform_policy", "get_platform_policy"]],
        expected_tool_args={
            "get_platform_policy": [
                {"platform": "Meta", "policy_type": "ad_format"},
                {"platform": "Meta", "policy_type": "content_restriction"},
            ]
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
                        "name": "get_platform_policy",
                        "arguments": {"platform": "Meta", "policy_type": "ad_format"},
                    },
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "get_platform_policy",
                        "arguments": {"platform": "Meta", "policy_type": "ad_format"},
                    },
                },
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
        {"role": "tool", "tool_call_id": "call_2", "content": "{}"},
        {"role": "assistant", "content": "已完成"},
    ]

    scores = evaluate_system_case(case, trace)

    assert scores["S2"] == 0.0
    assert scores["S5"] == 0.0
