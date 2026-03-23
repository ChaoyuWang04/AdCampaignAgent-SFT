#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Split an AdCampaign dataset into stratified train/test sets by workflow and scene.
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Split AdCampaign dataset into train/test subsets")
    parser.add_argument("--input", required=True, help="Path to source JSON dataset")
    parser.add_argument("--train-output", default="", help="Optional train output path")
    parser.add_argument("--test-output", default="", help="Optional test output path")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Train split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def _group_key(item):
    meta = item.get("_meta", {})
    workflow = meta.get("workflow_name") or item.get("workflow_name") or "unknown_workflow"
    scene = meta.get("scene_tag") or item.get("scene_tag") or "unknown_scene"
    return workflow, scene


def main():
    args = parse_args()
    input_path = Path(args.input)
    data = json.loads(input_path.read_text(encoding="utf-8"))

    grouped = defaultdict(list)
    for item in data:
        grouped[_group_key(item)].append(item)

    random.seed(args.seed)
    train_data = []
    test_data = []

    for items in grouped.values():
        random.shuffle(items)
        split_idx = int(len(items) * args.train_ratio)
        if split_idx == 0 and len(items) > 1:
            split_idx = 1
        train_data.extend(items[:split_idx])
        test_data.extend(items[split_idx:])

    random.shuffle(train_data)
    random.shuffle(test_data)

    train_output = Path(args.train_output) if args.train_output else input_path.with_name(f"{input_path.stem}_train.json")
    test_output = Path(args.test_output) if args.test_output else input_path.with_name(f"{input_path.stem}_test.json")

    train_output.write_text(json.dumps(train_data, ensure_ascii=False, indent=2), encoding="utf-8")
    test_output.write_text(json.dumps(test_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Train set: {len(train_data)} -> {train_output}")
    print(f"Test set: {len(test_data)} -> {test_output}")


if __name__ == "__main__":
    main()
