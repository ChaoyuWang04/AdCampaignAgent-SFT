#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smoke test for AdCampaign function-calling style message generation.
"""

import importlib.util
import json
from pathlib import Path


def load_converter_module():
    module_path = Path(__file__).resolve().parents[2] / "datapipeline" / "2_convert_data_message.py"
    spec = importlib.util.spec_from_file_location("ad_message_converter", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main():
    module = load_converter_module()

    seeds = [
        {
            "workflow": 1,
            "workflow_name": "Creative Search",
            "user_query": "Find top-performing UGC-style creatives for puzzle games on TikTok.",
            "needs_clarification": False,
            "scene_tag": "creative_search",
            "tool_chain": ["search_trending_creatives", "get_trending_hooks"],
            "platform": "Tiktok",
            "game_genre": "puzzle",
            "region": "SEA",
            "campaign_id": "CMP_5012",
            "app_id": "com.gamestar.puzzle04",
            "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
            "roas_baseline_d7": 0.75,
            "roas_baseline_d30": 1.1,
            "ret_baseline_d1": 0.38,
            "ret_baseline_d7": 0.14,
        },
        {
            "workflow": 7,
            "workflow_name": "Refusal",
            "user_query": "Delete every active campaign in our account right now.",
            "needs_clarification": False,
            "scene_tag": "unauthorized_operation",
            "refusal_type": "unauthorized_operation",
            "tool_chain": [],
            "platform": "Meta",
            "game_genre": "casual",
            "region": "US",
            "campaign_id": "CMP_9001",
            "app_id": "com.funplay.casual05",
            "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
            "roas_baseline_d7": 0.75,
            "roas_baseline_d30": 1.1,
            "ret_baseline_d1": 0.35,
            "ret_baseline_d7": 0.12,
        },
    ]

    print("Testing AdCampaign function-calling message generation")
    print("=" * 60)

    for idx, seed in enumerate(seeds, start=1):
        print(f"\nCase {idx}: {seed['workflow_name']}")
        record = module.build_conversation(seed)
        messages = record["messages"]
        print(f"Total messages: {len(messages)}")
        for message in messages:
            if message["role"] == "assistant" and "tool_calls" in message:
                tool_names = [call["function"]["name"] for call in message["tool_calls"]]
                print(f"assistant tool_calls -> {tool_names}")
            else:
                preview = message.get("content", "")
                preview = preview if len(preview) <= 120 else preview[:117] + "..."
                print(f"{message['role']}: {preview}")

        print("Record preview:")
        print(json.dumps(record["_meta"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
