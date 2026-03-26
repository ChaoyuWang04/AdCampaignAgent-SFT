#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Split Ad Agent seed records into stratified train/test datasets.
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


DEFAULT_INPUT = Path("data/raw/ad_agent_seeds_latest.json")
DEFAULT_TRAIN = Path("data/processed/ad_agent_seeds_train.json")
DEFAULT_TEST = Path("data/processed/ad_agent_seeds_test.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split Ad Agent seed dataset into train/test")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input seed JSON file")
    parser.add_argument("--train-output", type=Path, default=DEFAULT_TRAIN, help="Train JSON output path")
    parser.add_argument("--test-output", type=Path, default=DEFAULT_TEST, help="Test JSON output path")
    parser.add_argument("--train-ratio", type=float, default=0.8, help="Train split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args()


def stratify_key(item: Dict) -> str:
    workflow_name = item.get("workflow_name", f"workflow_{item.get('workflow', 'unknown')}")
    scene_tag = item.get("scene_tag", "unknown_scene")
    clarify_flag = "clarify" if item.get("needs_clarification") else "direct"
    return f"{workflow_name} | {scene_tag} | {clarify_flag}"


def load_records(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise ValueError("Input dataset must be a JSON array")
    return payload


def save_records(path: Path, records: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def split_dataset(args: argparse.Namespace) -> None:
    records = load_records(args.input)
    print(f"Loaded records: {len(records)}")

    grouped = defaultdict(list)
    for item in records:
        grouped[stratify_key(item)].append(item)

    print("\nSource distribution:")
    print("=" * 72)
    for key, items in sorted(grouped.items()):
        print(f"{key}: {len(items)}")

    random.seed(args.seed)
    train_records: List[Dict] = []
    test_records: List[Dict] = []
    train_stats: Dict[str, int] = {}
    test_stats: Dict[str, int] = {}

    for key, items in grouped.items():
        random.shuffle(items)
        train_size = int(len(items) * args.train_ratio)
        if len(items) > 1:
            train_size = min(max(train_size, 1), len(items) - 1)
        train_slice = items[:train_size]
        test_slice = items[train_size:]
        train_records.extend(train_slice)
        test_records.extend(test_slice)
        train_stats[key] = len(train_slice)
        test_stats[key] = len(test_slice)

    random.shuffle(train_records)
    random.shuffle(test_records)

    save_records(args.train_output, train_records)
    save_records(args.test_output, test_records)

    print("\nSplit complete")
    print("=" * 72)
    print(f"Train: {len(train_records)} -> {args.train_output}")
    print(f"Test : {len(test_records)} -> {args.test_output}")

    print("\nTrain distribution:")
    for key in sorted(train_stats):
        print(f"{key}: {train_stats[key]}")

    print("\nTest distribution:")
    for key in sorted(test_stats):
        print(f"{key}: {test_stats[key]}")


if __name__ == "__main__":
    split_dataset(parse_args())
