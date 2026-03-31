#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Smoke test for Ad Agent seed generation."""

import importlib.util
from pathlib import Path


GENERATOR_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "0_generate_base_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_base_dataset", GENERATOR_PATH)
generate_base_dataset = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generate_base_dataset)


def main():
    print("测试 Ad Agent 种子数据生成...")
    generator = generate_base_dataset.AdDatasetGenerator()
    generator.progress["total"] = 8

    test_data = []
    test_data.extend(generator.gen_workflow1_creative_search(2))
    test_data.extend(generator.gen_workflow2_upload(2))
    test_data.extend(generator.gen_workflow4_deep_analysis(2))
    test_data.extend(generator.gen_workflow5_anomaly(2))

    print(f"生成了 {len(test_data)} 条测试数据")

    for index, item in enumerate(test_data[:4], start=1):
        print(f"\n示例 {index}:")
        print(f"workflow: {item['workflow_name']}")
        print(f"user_query: {item['user_query']}")
        print(f"scene_tag: {item['scene_tag']}")
        print(f"tool_chain: {item['tool_chain']}")


if __name__ == "__main__":
    main()
