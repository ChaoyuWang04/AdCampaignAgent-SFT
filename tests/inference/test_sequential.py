#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Manual sequential tool-chain test for Ad Agent dataset conversion."""

import importlib.util
from pathlib import Path


CONVERT_DATASET_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "2_convert_dataset.py"
SPEC = importlib.util.spec_from_file_location("convert_dataset", CONVERT_DATASET_PATH)
convert_dataset = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(convert_dataset)


def test_ad_workflow_sequential():
    """测试广告投放工作流中的顺序工具调用"""

    test_data = [
        {
            "workflow": 2,
            "workflow_name": "素材上传",
            "user_role": "UA Manager",
            "platform": "Meta",
            "game_genre": "casual",
            "region": "US",
            "campaign_id": "CMP_2048",
            "app_id": "APP_9001",
            "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
            "roas_baseline_d7": 0.85,
            "roas_baseline_d30": 1.20,
            "ret_baseline_d1": 0.35,
            "ret_baseline_d7": 0.12,
            "user_query": "把这批新素材上传到 CMP_2048",
            "needs_clarification": False,
            "clarification_reason": None,
            "clarification_answer": None,
            "scene_tag": "upload_success",
            "tool_chain": ["validate_creative_spec", "upload_creative_asset"],
            "tool_plan": [
                {"mode": "serial", "tools": ["validate_creative_spec"]},
                {"mode": "serial", "tools": ["upload_creative_asset"]},
            ],
            "has_parallel": False,
            "refusal_type": None,
        },
        {
            "workflow": 5,
            "workflow_name": "异常诊断与优化",
            "user_role": "Growth Lead",
            "platform": "Meta",
            "game_genre": "puzzle",
            "region": "US",
            "campaign_id": "CMP_3099",
            "app_id": "APP_8221",
            "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
            "roas_baseline_d7": 0.80,
            "roas_baseline_d30": 1.20,
            "ret_baseline_d1": 0.38,
            "ret_baseline_d7": 0.14,
            "user_query": "CMP_3099 最近效果异常，帮我看下原因并给建议。",
            "needs_clarification": False,
            "clarification_reason": None,
            "clarification_answer": None,
            "scene_tag": "roas_warning",
            "tool_chain": ["detect_anomalies", "get_optimization_playbook"],
            "tool_plan": [
                {"mode": "serial", "tools": ["detect_anomalies"]},
                {"mode": "serial", "tools": ["get_optimization_playbook"]},
            ],
            "has_parallel": False,
            "refusal_type": None,
        },
        {
            "workflow": 4,
            "workflow_name": "多维深度分析",
            "user_role": "UA Manager",
            "platform": "Google",
            "game_genre": "strategy",
            "region": "JP",
            "campaign_id": "CMP_9012",
            "app_id": "APP_1177",
            "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
            "roas_baseline_d7": 0.90,
            "roas_baseline_d30": 1.40,
            "ret_baseline_d1": 0.30,
            "ret_baseline_d7": 0.10,
            "user_query": "帮我对 CMP_9012 做深度分析，看 campaign、creative 和 benchmark。",
            "needs_clarification": False,
            "clarification_reason": None,
            "clarification_answer": None,
            "scene_tag": "healthy",
            "tool_chain": ["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"],
            "tool_plan": [
                {"mode": "parallel", "tools": ["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"]},
            ],
            "has_parallel": True,
            "refusal_type": None,
        },
    ]

    print("\n测试广告投放工作流的工具调用...")
    for index, item in enumerate(test_data, start=1):
        print(f"\n--- 测试数据 {index} ---")
        print(f"用户问题: {item['user_query']}")
        print(f"工具链: {item['tool_chain']}")

        result = convert_dataset.build_record(item)
        conversation = result["messages"]
        print(f"对话轮数: {len(conversation)}")

        assistant_msgs = [msg for msg in conversation if msg["role"] == "assistant" and "tool_calls" in msg]
        flattened_tools = []
        for msg in assistant_msgs:
            flattened_tools.extend(tool_call["function"]["name"] for tool_call in msg["tool_calls"])

        assert flattened_tools[:len(item["tool_chain"])] == item["tool_chain"]


if __name__ == "__main__":
    test_ad_workflow_sequential()
