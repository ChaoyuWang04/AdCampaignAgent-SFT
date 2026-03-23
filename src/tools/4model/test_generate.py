#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Smoke test for the AdCampaign seed-data generator.
"""

import importlib.util
import json
from pathlib import Path


def load_seed_module():
    module_path = Path(__file__).resolve().parents[2] / "datapipeline" / "1_ad_gen_data.py"
    spec = importlib.util.spec_from_file_location("ad_seed_generator", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main():
    module = load_seed_module()
    generator = module.AdDatasetGenerator("en")

    print("Testing AdCampaign seed generation...")
    test_data = []
    test_data.extend(generator.gen_workflow1_creative_search(2))
    test_data.extend(generator.gen_workflow3_single_query(1))
    test_data.extend(generator.gen_workflow4_deep_analysis(1))
    test_data.extend(generator.gen_workflow7_refusal(1))

    print(f"Generated {len(test_data)} seed records")
    for i, item in enumerate(test_data[:3], start=1):
        print(f"\nSample {i}:")
        print(json.dumps(item, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
