#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Manual sequential tool-chain test for Ad Agent dataset conversion."""

import os
import sys

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.datapipeline.convert_dataset import build_record

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
            "refusal_type": None,
        }
    ]

    print("\n测试广告投放工作流的顺序工具调用...")
    for i, item in enumerate(test_data):
        print(f"\n--- 测试数据 {i+1} ---")
        print(f"用户问题: {item['user_query']}")
        print(f"工具链: {item['tool_chain']}")

        try:
            result = build_record(item, lang="zh", output_format="message")
            if result:
                print("✅ 转换成功")
                conversation = result["messages"]
                print(f"对话轮数: {len(conversation)}")

                tool_call_count = 0
                for j, msg in enumerate(conversation):
                    role = msg["role"]
                    if role == "system":
                        print(f"  {j+1}. {role}: [系统提示词]")
                    elif role == "user":
                        print(f"  {j+1}. {role}: {msg['content'][:50]}...")
                    elif role == "assistant":
                        if "tool_calls" in msg:
                            tool_call_count += 1
                            tool_names = [tc["function"]["name"] for tc in msg["tool_calls"]]
                            print(f"  {j+1}. {role}: [工具调用{tool_call_count}] {tool_names}")
                        else:
                            print(f"  {j+1}. {role}: {msg['content'][:50]}...")
                    elif role == "tool":
                        print(f"  {j+1}. {role}: [工具结果]")

                assistant_msgs = [msg for msg in conversation if msg["role"] == "assistant" and "tool_calls" in msg]
                flattened_tools = []
                for msg in assistant_msgs:
                    flattened_tools.extend(tc["function"]["name"] for tc in msg["tool_calls"])

                expected_chain = item["tool_chain"]
                if flattened_tools[: len(expected_chain)] == expected_chain:
                    print("✅ 检测到符合预期的顺序工具调用")
                else:
                    print("⚠️  工具调用顺序与预期不一致")
                    print(f"    expected: {expected_chain}")
                    print(f"    actual:   {flattened_tools}")
            else:
                print("❌ 转换失败")
        except Exception as e:
            print(f"❌ 转换出错: {e}")
            import traceback
            traceback.print_exc()

    print("\n测试完成")

if __name__ == "__main__":
    test_ad_workflow_sequential()
