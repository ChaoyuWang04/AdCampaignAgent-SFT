#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试 LoRA merge 脚本的参数约束。"""

import os
import sys

import pytest

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.train import merge_lora_into_base


def test_parse_args_requires_explicit_paths(monkeypatch) -> None:
    """merge 脚本应要求显式传入 base、adapter 和 output 路径。"""
    monkeypatch.setattr(
        "sys.argv",
        [
            "merge_lora_into_base.py",
        ],
    )

    with pytest.raises(SystemExit):
        merge_lora_into_base.parse_args()


def test_parse_args_accepts_explicit_paths(monkeypatch) -> None:
    """显式传入路径时应能正常解析参数。"""
    monkeypatch.setattr(
        "sys.argv",
        [
            "merge_lora_into_base.py",
            "--base_model",
            "/tmp/base",
            "--adapter_path",
            "/tmp/adapter",
            "--output_dir",
            "/tmp/output",
        ],
    )

    args = merge_lora_into_base.parse_args()

    assert args.base_model == "/tmp/base"
    assert args.adapter_path == "/tmp/adapter"
    assert args.output_dir == "/tmp/output"
