import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "benchmark" / "benchmark_utils.py"
SPEC = importlib.util.spec_from_file_location("benchmark_utils", MODULE_PATH)
benchmark_utils = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(benchmark_utils)


def _assistant_trace(text: str) -> list[dict]:
    return [{"role": "assistant", "content": text}]


def test_infer_behavior_recognizes_permission_refusal_variants():
    text = "抱歉，删除/修改账户级数据属于高风险操作，超出了我的权限范围。为避免不可逆的影响，此类操作请通过平台后台或联系您的账户经理处理。"

    assert benchmark_utils.infer_behavior(_assistant_trace(text)) == "reject"


def test_infer_behavior_recognizes_scope_refusal_without_exact_phrase_match():
    text = "抱歉，我是专注于移动游戏广告投放的 AI 助手，这个问题超出了我的服务范围。"

    assert benchmark_utils.infer_behavior(_assistant_trace(text)) == "reject"


def test_infer_behavior_prioritizes_reject_over_clarify_when_both_signals_exist():
    text = "请告知您的需求，但此操作超出了我的权限范围。"

    assert benchmark_utils.infer_behavior(_assistant_trace(text)) == "reject"


def test_infer_behavior_keeps_tool_calls_as_tool_call_even_if_risk_is_mentioned():
    trace = [
        {
            "role": "assistant",
            "content": "我先分析该 campaign 的 ROAS 风险。",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_campaign_metrics", "arguments": "{}"},
                }
            ],
        }
    ]

    assert benchmark_utils.infer_behavior(trace) == "tool_call"
