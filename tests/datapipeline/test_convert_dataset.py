import importlib.util
from pathlib import Path


CONVERT_DATASET_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "2_convert_dataset.py"
SPEC = importlib.util.spec_from_file_location("convert_dataset", CONVERT_DATASET_PATH)
convert_dataset = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(convert_dataset)


SEED = {
    "workflow": 3,
    "workflow_name": "单指标效果查询",
    "user_query": "检查 campaign 表现",
    "needs_clarification": False,
    "scene_tag": "healthy",
    "tool_chain": ["get_campaign_metrics"],
    "platform": "Meta",
    "game_genre": "casual",
    "region": "US",
    "campaign_id": "CMP_1234",
    "app_id": "com.test.game",
    "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
    "roas_baseline_d7": 0.75,
    "roas_baseline_d30": 1.10,
    "ret_baseline_d1": 0.35,
    "ret_baseline_d7": 0.12,
    "tool_plan": [{"mode": "serial", "tools": ["get_campaign_metrics"]}],
    "has_parallel": False,
}


def test_build_record_returns_message_format_only():
    message_record = convert_dataset.build_record(SEED)

    assert "messages" in message_record
    assert message_record["messages"][0]["role"] == "system"
    assert "tool_calls" in message_record["messages"][2]
    assert "conversations" not in message_record


def test_build_record_emits_parallel_tool_calls_in_single_assistant_turn():
    seed = {
        **SEED,
        "workflow": 4,
        "workflow_name": "多维深度分析",
        "tool_plan": [
            {"mode": "parallel", "tools": ["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"]}
        ],
        "tool_chain": ["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"],
        "has_parallel": True,
    }

    record = convert_dataset.build_record(seed)
    assistant_tool_turns = [
        message for message in record["messages"]
        if message["role"] == "assistant" and message.get("tool_calls")
    ]

    assert len(assistant_tool_turns) == 1
    assert len(assistant_tool_turns[0]["tool_calls"]) == 3
    assert [call["function"]["name"] for call in assistant_tool_turns[0]["tool_calls"]] == [
        "get_campaign_metrics",
        "get_creative_performance",
        "get_benchmark_data",
    ]


def test_derive_output_path_uses_ready2train_root(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    script_path = repo_root / "src" / "datapipeline" / "2_convert_dataset.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test stub\n", encoding="utf-8")

    monkeypatch.setattr(convert_dataset.Path, "resolve", lambda self: script_path)

    input_path = repo_root / "data" / "raw" / "ad_agent_seeds_demo_zh.json"

    output_path = convert_dataset.derive_output_path(input_path)

    assert output_path == repo_root / "data" / "ready2train" / "ad_agent_sft_demo_zh.json"


def test_resolve_input_path_uses_processed_directory(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    script_path = repo_root / "src" / "datapipeline" / "2_convert_dataset.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test stub\n", encoding="utf-8")
    target_file = repo_root / "data" / "processed" / "ad_agent_seeds_demo_zh_train.json"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(convert_dataset.Path, "resolve", lambda self: script_path)

    resolved = convert_dataset.resolve_input_path("ad_agent_seeds_demo_zh_train.json")

    assert resolved == target_file
