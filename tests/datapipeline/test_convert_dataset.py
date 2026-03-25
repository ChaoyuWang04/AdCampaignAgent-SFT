import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    )

from src.datapipeline import convert_dataset


SEED = {
    "workflow": 3,
    "workflow_name": "Single Metric Query",
    "user_query": "Check campaign performance",
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
}


def test_build_record_supports_message_and_sharegpt():
    message_record = convert_dataset.build_record(SEED, "en", "message")
    sharegpt_record = convert_dataset.build_record(SEED, "en", "sharegpt")

    assert "messages" in message_record
    assert message_record["messages"][0]["role"] == "system"
    assert "tool_calls" in message_record["messages"][2]

    assert "conversations" in sharegpt_record
    assert sharegpt_record["conversations"][0]["from"] == "system"
    assert sharegpt_record["conversations"][2]["value"].startswith("<tool_call>")


def test_derive_output_path_uses_ready2train_subdirectories(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    script_path = repo_root / "src" / "datapipeline" / "convert_dataset.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test stub\n", encoding="utf-8")

    monkeypatch.setattr(
        "src.datapipeline.convert_dataset.Path.resolve",
        lambda self: script_path,
    )

    input_path = repo_root / "data" / "raw" / "ad_agent_seeds_demo_en.json"

    message_path = convert_dataset.derive_output_path(input_path, "message")
    sharegpt_path = convert_dataset.derive_output_path(input_path, "sharegpt")

    assert message_path == repo_root / "data" / "ready2train" / "message" / "ad_agent_sft_demo_en_message.json"
    assert sharegpt_path == repo_root / "data" / "ready2train" / "sharegpt" / "ad_agent_sft_demo_en_sharegpt.json"
