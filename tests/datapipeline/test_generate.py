#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Smoke test for Ad Agent seed generation."""

import os
import sys

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.datapipeline.generate_base_dataset import AdDatasetGenerator

def main():
    print("测试 Ad Agent 种子数据生成...")
    generator = AdDatasetGenerator("zh")
    generator.progress["total"] = 8

    test_data = []
    test_data.extend(generator.gen_workflow1_creative_search(2))
    test_data.extend(generator.gen_workflow2_upload(2))
    test_data.extend(generator.gen_workflow4_deep_analysis(2))
    test_data.extend(generator.gen_workflow5_anomaly(2))

    print(f"生成了 {len(test_data)} 条测试数据")

    for i, item in enumerate(test_data[:4], start=1):
        print(f"\n示例 {i}:")
        print(f"workflow: {item['workflow_name']}")
        print(f"user_query: {item['user_query']}")
        print(f"scene_tag: {item['scene_tag']}")
        print(f"tool_chain: {item['tool_chain']}")

if __name__ == "__main__":
    main()
