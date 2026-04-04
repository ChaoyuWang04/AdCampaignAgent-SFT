from src.benchmark.benchmark_schema import BenchmarkCase
from src.benchmark.eval_content import evaluate_content_case


def _tool_trace(tool_name: str, arguments: dict, final_text: str = "已完成") -> list[dict]:
    return [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "帮我看下表现"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
        {"role": "assistant", "content": final_text},
    ]


def test_c1_treats_expected_args_as_subset_of_actual_args() -> None:
    case = BenchmarkCase(
        id="std_subset",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天表现",
        expected_behavior="tool_call",
        expected_tools=["get_campaign_metrics"],
        expected_tool_args={"get_campaign_metrics": {"campaign_id": "CMP_2048"}},
    )
    trace = _tool_trace(
        "get_campaign_metrics",
        {
            "campaign_id": "CMP_2048",
            "metrics": ["impressions", "clicks", "roas_d7"],
            "date_range": {"preset": "last_7_days"},
        },
    )

    scores = evaluate_content_case(case, trace)

    assert scores["C1"] == 1.0
    assert scores["C2"] == 1.0


def test_c1_fails_when_expected_field_value_differs() -> None:
    case = BenchmarkCase(
        id="std_mismatch",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天表现",
        expected_behavior="tool_call",
        expected_tools=["get_campaign_metrics"],
        expected_tool_args={"get_campaign_metrics": {"campaign_id": "CMP_2048"}},
    )
    trace = _tool_trace(
        "get_campaign_metrics",
        {"campaign_id": "CMP_9999", "metrics": ["roas_d7"]},
    )

    scores = evaluate_content_case(case, trace)

    assert scores["C1"] == 0.0
    assert scores["C2"] == 0.0


def test_c2_keeps_partial_field_accuracy_when_only_some_gold_fields_match() -> None:
    case = BenchmarkCase(
        id="std_partial",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天表现",
        expected_behavior="tool_call",
        expected_tools=["get_campaign_metrics"],
        expected_tool_args={
            "get_campaign_metrics": {
                "campaign_id": "CMP_2048",
                "platform": "Meta",
            }
        },
    )
    trace = _tool_trace(
        "get_campaign_metrics",
        {
            "campaign_id": "CMP_2048",
            "platform": "Google Ads",
            "metrics": ["roas_d7"],
        },
    )

    scores = evaluate_content_case(case, trace)

    assert scores["C1"] == 0.0
    assert scores["C2"] == 0.5


def test_content_scores_repeated_same_tool_calls_against_expected_argument_list() -> None:
    case = BenchmarkCase(
        id="par_repeated_args",
        case_type="parallel",
        user_input="同时帮我查一下 CMP_1024 和 CMP_2048 的核心指标。",
        expected_behavior="tool_call",
        expected_tools=["get_campaign_metrics", "get_campaign_metrics"],
        expected_tool_args={
            "get_campaign_metrics": [
                {"campaign_id": "CMP_1024"},
                {"campaign_id": "CMP_2048"},
            ]
        },
    )
    trace = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": case.user_input},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "get_campaign_metrics",
                        "arguments": {"campaign_id": "CMP_1024"},
                    },
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "get_campaign_metrics",
                        "arguments": {"campaign_id": "CMP_2048"},
                    },
                },
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "{}"},
        {"role": "tool", "tool_call_id": "call_2", "content": "{}"},
        {"role": "assistant", "content": "已完成"},
    ]

    scores = evaluate_content_case(case, trace)

    assert scores["C1"] == 1.0
    assert scores["C2"] == 1.0
