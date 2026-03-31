#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试 split_dataset 的交互式输入与输出路径推导逻辑。"""

import importlib.util
import json
from argparse import Namespace
from pathlib import Path


SPLIT_DATASET_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "1_split_dataset.py"
SPEC = importlib.util.spec_from_file_location("split_dataset", SPLIT_DATASET_PATH)
split_dataset_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(split_dataset_module)


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
    input_path = tmp_path / "data" / "raw" / "ad_agent_seeds_20260326_zh.json"

    train_output, test_output = split_dataset_module.build_output_paths(input_path)

    assert train_output.name == "ad_agent_seeds_20260326_zh_train.json"
    assert test_output.name == "ad_agent_seeds_20260326_zh_test.json"
    assert train_output.parent.name == "processed"
    assert test_output.parent.name == "processed"


def test_split_logic_is_stable_for_chinese_records(tmp_path: Path) -> None:
    """中文 seed 文件应复用同一套 split 逻辑。"""
    records = [
        {"workflow_name": "素材搜寻", "scene_tag": "healthy", "needs_clarification": False},
        {"workflow_name": "素材搜寻", "scene_tag": "healthy", "needs_clarification": False},
    ]
    input_path = tmp_path / "zh.json"
    input_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    loaded = split_dataset_module.load_records(input_path)
    group_key = split_dataset_module.stratify_key(loaded[0])

    assert group_key == "素材搜寻 | healthy | direct"


def test_split_dataset_rounds_small_strata_and_keeps_singletons_in_train(
    monkeypatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    raw_dir = repo_root / "data" / "raw"
    processed_dir = repo_root / "data" / "processed"
    raw_dir.mkdir(parents=True)
    processed_dir.mkdir(parents=True)

    input_path = raw_dir / "ad_agent_seeds_sample_zh.json"
    records = [
        {"workflow_name": "素材搜寻", "scene_tag": "healthy", "needs_clarification": False, "id": 1},
        {"workflow_name": "素材搜寻", "scene_tag": "healthy", "needs_clarification": False, "id": 2},
        {"workflow_name": "素材搜寻", "scene_tag": "healthy", "needs_clarification": False, "id": 3},
        {"workflow_name": "知识问答", "scene_tag": "knowledge_base", "needs_clarification": False, "id": 4},
    ]
    input_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(split_dataset_module, "repo_root", lambda: repo_root)
    monkeypatch.setattr(split_dataset_module, "prompt_input_file", lambda: input_path)

    split_dataset_module.split_dataset(Namespace(train_ratio=0.9, seed=42))

    train_path = processed_dir / "ad_agent_seeds_sample_zh_train.json"
    test_path = processed_dir / "ad_agent_seeds_sample_zh_test.json"
    train_records = json.loads(train_path.read_text(encoding="utf-8"))
    test_records = json.loads(test_path.read_text(encoding="utf-8"))

    assert len(train_records) == 3
    assert len(test_records) == 1
    assert {record["id"] for record in train_records} | {record["id"] for record in test_records} == {1, 2, 3, 4}
    assert any(record["id"] == 4 for record in train_records)
    assert all(record["id"] != 4 for record in test_records)
