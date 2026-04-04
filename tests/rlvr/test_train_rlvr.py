#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))


def test_validate_args_rejects_num_generations_below_two():
    from src.rlvr.train_rlvr import parse_args, validate_args

    args = parse_args(
        [
            "--model_path",
            "models/Qwen3-1.7B",
            "--output_dir",
            "outputs/test-rlvr",
            "--num_generations",
            "1",
        ]
    )

    with pytest.raises(ValueError, match="num_generations"):
        validate_args(args)


def test_build_grpo_config_saves_checkpoints_multiple_times_for_smoke_runs():
    from src.rlvr.train_rlvr import build_grpo_config, parse_args

    args = parse_args(
        [
            "--model_path",
            "models/Qwen3-1.7B",
            "--output_dir",
            "outputs/test-rlvr",
            "--max_steps",
            "20",
        ]
    )

    config = build_grpo_config(args)

    assert config.save_steps == 5
