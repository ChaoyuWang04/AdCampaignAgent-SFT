#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RLVR 训练数据入口。

职责：
- 从 benchmark 数据目录读取全部 case
- 按 `case_type` 做分层切分
- 提供 `rlvr_train / rlvr_eval / all` 三种视图

输入：
- benchmark JSON 文件
- split 名称
- 随机种子

输出：
- `list[BenchmarkCase]`

和 GRPO / RLVR 的关系：
- GRPO 训练需要一个稳定、可重复采样的任务池
- 这里不做 reward，也不做 prompt 拼接，只负责训练任务从哪里来
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from pathlib import Path
import sys

from src.common.project_paths import data_dir

try:
    from src.benchmark.benchmark_schema import BenchmarkCase, load_cases
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))
    from benchmark_schema import BenchmarkCase, load_cases


DEFAULT_RLVR_DATA_DIR = data_dir() / "rlvr"
DEFAULT_TRAIN_CASES_DIR = DEFAULT_RLVR_DATA_DIR / "train_cases"
DEFAULT_EVAL_CASES_DIR = DEFAULT_RLVR_DATA_DIR / "eval_cases"
DEFAULT_SPLIT_SEED = 42
TRAIN_SPLIT = "rlvr_train"
EVAL_SPLIT = "rlvr_eval"


def _load_all_cases(data_dir: Path) -> list[BenchmarkCase]:
    """读取 benchmark 目录下的全部 case 文件，并合并成一个列表。"""
    cases: list[BenchmarkCase] = []
    for path in sorted(data_dir.glob("test_*.json")):
        cases.extend(load_cases(path))
    return cases


def _load_split_cases(split_dir: Path) -> list[BenchmarkCase]:
    """读取一个 RLVR split 目录下的全部 case 文件。"""
    cases: list[BenchmarkCase] = []
    for path in sorted(split_dir.glob("test_*.json")):
        cases.extend(load_cases(path))
    return sorted(cases, key=lambda case: case.id)


def _compute_eval_counts(group_sizes: dict[str, int], eval_size: int) -> dict[str, int]:
    """按比例计算各 case_type 应分配到 eval 集的样本数。"""
    total = sum(group_sizes.values())
    if total == 0:
        return {key: 0 for key in group_sizes}

    exact = {
        key: (size / total) * eval_size
        for key, size in group_sizes.items()
    }
    counts = {key: math.floor(value) for key, value in exact.items()}
    remaining = eval_size - sum(counts.values())

    remainders = sorted(
        ((exact[key] - counts[key], key) for key in group_sizes),
        reverse=True,
    )
    for _, key in remainders[:remaining]:
        counts[key] += 1
    return counts


def _build_stratified_splits(
    cases: list[BenchmarkCase],
    eval_size: int,
    seed: int,
) -> tuple[list[BenchmarkCase], list[BenchmarkCase]]:
    """
    对 benchmark case 做分层切分。

    训练集用于 RLVR rollout 更新，eval 集保留为 holdout 验证。
    """
    grouped: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for case in cases:
        grouped[case.case_type].append(case)

    rng = random.Random(seed)
    for items in grouped.values():
        rng.shuffle(items)

    eval_counts = _compute_eval_counts(
        {case_type: len(items) for case_type, items in grouped.items()},
        eval_size=eval_size,
    )

    train_cases: list[BenchmarkCase] = []
    eval_cases: list[BenchmarkCase] = []
    for case_type in sorted(grouped):
        items = grouped[case_type]
        split_at = eval_counts[case_type]
        eval_cases.extend(items[:split_at])
        train_cases.extend(items[split_at:])

    train_cases.sort(key=lambda case: case.id)
    eval_cases.sort(key=lambda case: case.id)
    return train_cases, eval_cases


def load_rlvr_cases(
    *,
    split: str,
    data_dir: str | Path = DEFAULT_RLVR_DATA_DIR,
    seed: int = DEFAULT_SPLIT_SEED,
) -> list[BenchmarkCase]:
    """统一加载 RLVR 所需的训练集、eval 集或全量 case。"""
    _ = seed
    data_path = Path(data_dir)
    train_cases = _load_split_cases(data_path / "train_cases")
    eval_cases = _load_split_cases(data_path / "eval_cases")

    if split == TRAIN_SPLIT:
        return train_cases
    if split == EVAL_SPLIT:
        return eval_cases
    if split == "all":
        return sorted(train_cases + eval_cases, key=lambda case: case.id)
    raise ValueError(f"Unsupported split: {split}")
