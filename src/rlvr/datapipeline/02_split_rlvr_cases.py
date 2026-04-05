#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split RLVR benchmark cases into stratified train/eval files."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.benchmark.benchmark_schema import BenchmarkCase, load_cases
from src.common.project_paths import data_dir


def stratify_key(case: BenchmarkCase) -> str:
    return f"{case.case_type}|{case.expected_behavior}"


def split_cases(cases: list[BenchmarkCase], *, train_ratio: float = 0.85, seed: int = 42) -> tuple[list[BenchmarkCase], list[BenchmarkCase]]:
    grouped: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for case in cases:
        grouped[stratify_key(case)].append(case)

    rng = random.Random(seed)
    train_cases: list[BenchmarkCase] = []
    eval_cases: list[BenchmarkCase] = []
    for items in grouped.values():
        items = list(items)
        rng.shuffle(items)
        if len(items) == 1:
            train_cases.extend(items)
            continue
        train_size = max(1, min(round(len(items) * train_ratio), len(items) - 1))
        train_cases.extend(items[:train_size])
        eval_cases.extend(items[train_size:])
    rng.shuffle(train_cases)
    rng.shuffle(eval_cases)
    return train_cases, eval_cases


def _group_by_case_type(cases: list[BenchmarkCase]) -> dict[str, list[BenchmarkCase]]:
    grouped: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for case in cases:
        key = f"test_{case.case_type}.json"
        grouped[key].append(case)
    return grouped


def _serialize(case: BenchmarkCase, split: str) -> dict:
    payload = asdict(case)
    payload["rlvr_split"] = split
    return payload


def save_split_cases(cases: list[BenchmarkCase], output_dir: Path, *, split: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_name, items in _group_by_case_type(cases).items():
        output_path = output_dir / file_name
        output_path.write_text(
            json.dumps([_serialize(case, split) for case in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def main(input_path: str | Path | None = None, *, train_ratio: float = 0.85, seed: int = 42) -> tuple[list[BenchmarkCase], list[BenchmarkCase]]:
    source_path = Path(input_path) if input_path is not None else data_dir() / "rlvr" / "processed" / "rlvr_cases.json"
    cases = load_cases(source_path)
    train_cases, eval_cases = split_cases(cases, train_ratio=train_ratio, seed=seed)
    base_dir = data_dir() / "rlvr"
    save_split_cases(train_cases, base_dir / "train_cases", split="train")
    save_split_cases(eval_cases, base_dir / "eval_cases", split="eval")
    return train_cases, eval_cases


if __name__ == "__main__":
    main()
