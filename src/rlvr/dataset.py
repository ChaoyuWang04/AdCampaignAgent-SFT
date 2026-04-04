#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RLVR 训练数据入口。

职责：
- 从 RLVR 预切分目录读取全部 case
- 提供 `rlvr_train / rlvr_eval / all` 三种视图

输入：
- RLVR 预切分 JSON 文件
- split 名称

输出：
- `list[BenchmarkCase]`

和 GRPO / RLVR 的关系：
- GRPO 训练需要一个稳定、可重复采样的任务池
- 这里不做 reward，也不做 prompt 拼接，只负责训练任务从哪里来
"""

from __future__ import annotations

from pathlib import Path
import sys

from src.common.project_paths import data_dir

try:
    from src.benchmark.benchmark_schema import BenchmarkCase, load_cases
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))
    from benchmark_schema import BenchmarkCase, load_cases


DEFAULT_RLVR_DATA_DIR = data_dir() / "rlvr"
TRAIN_SPLIT = "rlvr_train"
EVAL_SPLIT = "rlvr_eval"


def _load_split_cases(split_dir: Path) -> list[BenchmarkCase]:
    """读取一个 RLVR split 目录下的全部 case 文件。"""
    cases: list[BenchmarkCase] = []
    for path in sorted(split_dir.glob("test_*.json")):
        cases.extend(load_cases(path))
    return sorted(cases, key=lambda case: case.id)


def load_rlvr_cases(
    *,
    split: str,
    data_dir: str | Path = DEFAULT_RLVR_DATA_DIR,
) -> list[BenchmarkCase]:
    """统一加载 RLVR 预切分的训练集、eval 集或全量 case。"""
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
