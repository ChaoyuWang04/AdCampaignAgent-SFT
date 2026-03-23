#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Validate sequential tool-calling structure for AdCampaign OpenAI-messages conversion.
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

    test_seeds = [
        {
            "workflow": 2,
            "workflow_name": "Creative Upload",
            "user_query": "Upload this new 15-second puzzle video to CMP_2048 after validation.",
            "needs_clarification": False,
            "scene_tag": "upload_success",
            "tool_chain": ["validate_creative_spec", "upload_creative_asset"],
            "platform": "Meta",
            "game_genre": "puzzle",
            "region": "US",
            "campaign_id": "CMP_2048",
            "app_id": "com.guru.puzzle08",
            "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
            "roas_baseline_d7": 0.8,
            "roas_baseline_d30": 1.2,
            "ret_baseline_d1": 0.38,
            "ret_baseline_d7": 0.14,
        },
        {
            "workflow": 5,
            "workflow_name": "Anomaly Diagnosis & Optimization",
            "user_query": "Please diagnose why CMP_7788 performance dropped this week and suggest fixes.",
            "needs_clarification": False,
            "scene_tag": "creative_fatigue",
            "tool_chain": ["detect_anomalies", "get_creative_performance", "get_optimization_playbook"],
            "platform": "Google",
            "game_genre": "casual",
            "region": "EU",
            "campaign_id": "CMP_7788",
            "app_id": "com.funplay.casual03",
            "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
            "roas_baseline_d7": 0.8,
            "roas_baseline_d30": 1.2,
            "ret_baseline_d1": 0.35,
            "ret_baseline_d7": 0.12,
        },
    ]

    for idx, seed in enumerate(test_seeds, start=1):
        print(f"\n--- Test case {idx} ---")
        print(f"User query: {seed['user_query']}")
        record = module.build_conversation(seed)
        messages = record["messages"]
        print(f"Message count: {len(messages)}")

        assistant_tool_turns = [
            message for message in messages
            if message["role"] == "assistant" and "tool_calls" in message
        ]
        tool_turns = [message for message in messages if message["role"] == "tool"]

        print(f"Assistant tool-call turns: {len(assistant_tool_turns)}")
        print(f"Tool result turns: {len(tool_turns)}")

        for message in assistant_tool_turns:
            tool_names = [call["function"]["name"] for call in message["tool_calls"]]
            print(f"  assistant -> {tool_names}")

        if len(assistant_tool_turns) != len(seed["tool_chain"]) or len(tool_turns) != len(seed["tool_chain"]):
            raise RuntimeError("Sequential tool-call structure does not match tool_chain length")

        print("Final assistant reply preview:")
        print(json.dumps(messages[-1], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
