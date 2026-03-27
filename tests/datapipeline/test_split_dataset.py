#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试 split_dataset 的交互式输入与输出路径推导逻辑。"""

import json
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    )

from src.datapipeline import split_dataset as split_dataset_module


def test_resolve_input_path_uses_user_provided_filename(monkeypatch, tmp_path: Path) -> None:
    """应根据用户输入的文件名在 data/raw 下定位 seed 文件。"""
    repo_root = tmp_path / "repo"
    data_raw = repo_root / "data" / "raw"
    data_raw.mkdir(parents=True)
    seed_file = data_raw / "ad_agent_seeds_20260326_zh.json"
    seed_file.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        split_dataset_module,
        "repo_root",
        lambda: repo_root,
    )
    monkeypatch.setattr("builtins.input", lambda _: "ad_agent_seeds_20260326_zh.json")

    resolved = split_dataset_module.prompt_input_file()

    assert resolved == seed_file


def test_build_output_paths_follow_input_filename(tmp_path: Path) -> None:
    """train/test 输出文件名应跟随输入文件名自动生成。"""
    input_path = tmp_path / "data" / "raw" / "ad_agent_seeds_20260326_en.json"

    train_output, test_output = split_dataset_module.build_output_paths(input_path)

    assert train_output.name == "ad_agent_seeds_20260326_en_train.json"
    assert test_output.name == "ad_agent_seeds_20260326_en_test.json"
    assert train_output.parent.name == "processed"
    assert test_output.parent.name == "processed"


def test_split_logic_is_language_agnostic(tmp_path: Path) -> None:
    """中英文 seed 文件都应复用同一套 split 逻辑。"""
    zh_records = [
        {"workflow_name": "素材搜寻", "scene_tag": "healthy", "needs_clarification": False},
        {"workflow_name": "素材搜寻", "scene_tag": "healthy", "needs_clarification": False},
    ]
    en_records = [
        {"workflow_name": "Creative Search", "scene_tag": "healthy", "needs_clarification": False},
        {"workflow_name": "Creative Search", "scene_tag": "healthy", "needs_clarification": False},
    ]
    zh_input = tmp_path / "zh.json"
    en_input = tmp_path / "en.json"
    zh_input.write_text(json.dumps(zh_records, ensure_ascii=False), encoding="utf-8")
    en_input.write_text(json.dumps(en_records, ensure_ascii=False), encoding="utf-8")

    zh_loaded = split_dataset_module.load_records(zh_input)
    en_loaded = split_dataset_module.load_records(en_input)

    zh_group_key = split_dataset_module.stratify_key(zh_loaded[0])
    en_group_key = split_dataset_module.stratify_key(en_loaded[0])

    assert zh_group_key.endswith("healthy | direct")
    assert en_group_key.endswith("healthy | direct")
