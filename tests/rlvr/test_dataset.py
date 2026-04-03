#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import Counter
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))

from benchmark_schema import BenchmarkCase


def test_load_rlvr_cases_reads_from_rlvr_data_directory():
    from src.rlvr.dataset import DEFAULT_RLVR_DATA_DIR, load_rlvr_cases

    cases = load_rlvr_cases(split="rlvr_train")

    assert DEFAULT_RLVR_DATA_DIR.name == "rlvr"
    assert (DEFAULT_RLVR_DATA_DIR / "train_cases").exists()
    assert (DEFAULT_RLVR_DATA_DIR / "eval_cases").exists()
    assert len(cases) == 75


def test_load_rlvr_cases_builds_stratified_train_split():
    from src.rlvr.dataset import load_rlvr_cases

    cases = load_rlvr_cases(split="rlvr_train")

    assert len(cases) == 75
    assert Counter(case.case_type for case in cases) == {
        "standard": 18,
        "oos": 21,
        "clarify": 14,
        "parallel": 11,
        "sequential": 11,
    }


def test_load_rlvr_cases_builds_stratified_eval_split():
    from src.rlvr.dataset import load_rlvr_cases

    cases = load_rlvr_cases(split="rlvr_eval")

    assert len(cases) == 30
    assert Counter(case.case_type for case in cases) == {
        "standard": 7,
        "oos": 9,
        "clarify": 6,
        "parallel": 4,
        "sequential": 4,
    }


def test_load_rlvr_cases_train_and_eval_are_disjoint_and_complete():
    from src.rlvr.dataset import load_rlvr_cases

    train_cases = load_rlvr_cases(split="rlvr_train")
    eval_cases = load_rlvr_cases(split="rlvr_eval")

    train_ids = {case.id for case in train_cases}
    eval_ids = {case.id for case in eval_cases}

    assert train_ids.isdisjoint(eval_ids)
    assert len(train_ids | eval_ids) == 105


def test_benchmark_case_supports_rlvr_extension_fields():
    case = BenchmarkCase(
        id="std_rlvr_ext",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天的投放表现。",
        rlvr_weight=2.5,
        rlvr_split="train",
        rlvr_tags=["tool_selection", "arg_accuracy"],
        rlvr_max_tool_rounds=2,
    )

    assert case.rlvr_weight == 2.5
    assert case.rlvr_split == "train"
    assert case.rlvr_tags == ["tool_selection", "arg_accuracy"]
    assert case.rlvr_max_tool_rounds == 2


def test_build_case_messages_returns_multi_turn_friendly_message_list():
    from src.rlvr.prompt_builder import build_case_messages

    case = BenchmarkCase(
        id="std_test",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天的投放表现。",
        context={"platform": "Meta", "campaign_id": "CMP_2048", "region": "US"},
        expected_behavior="tool_call",
    )

    messages = build_case_messages(case)

    assert isinstance(messages, list)
    assert messages == [
        {
            "role": "system",
            "content": messages[0]["content"],
        },
        {
            "role": "user",
            "content": "帮我看一下 CMP_2048 最近 7 天的投放表现。",
        },
    ]
    assert "广告投放上下文" in messages[0]["content"]
    assert "platform: Meta" in messages[0]["content"]
    assert "campaign_id: CMP_2048" in messages[0]["content"]
    assert "你是一个专业的移动游戏广告投放 AI 助手" in messages[0]["content"]


def test_build_case_messages_keeps_extension_point_for_future_history():
    from src.rlvr.prompt_builder import build_case_messages

    case = BenchmarkCase(
        id="clarify_test",
        case_type="clarify",
        user_input="帮我上传素材。",
        context={"platform": "Meta"},
        expected_behavior="clarify",
    )
    history = [
        {"role": "assistant", "content": "请提供要上传的素材文件路径。"},
        {"role": "user", "content": "assets/casual_video_03.mp4"},
    ]

    messages = build_case_messages(case, history=history)

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[2:] == history
