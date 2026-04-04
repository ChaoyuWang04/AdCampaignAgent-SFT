#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import Counter
import inspect
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


def test_load_rlvr_cases_seed_does_not_change_precomputed_split():
    from src.rlvr.dataset import load_rlvr_cases

    assert "seed" not in inspect.signature(load_rlvr_cases).parameters


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


def test_build_case_messages_reuses_cached_system_prompt(monkeypatch):
    from pathlib import Path
    import src.rlvr.prompt_builder as prompt_builder

    case = BenchmarkCase(
        id="std_cached_prompt",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天的投放表现。",
        context={"platform": "Meta"},
    )
    read_count = {"value": 0}

    original_read_text = Path.read_text

    def counting_read_text(path_self, *args, **kwargs):
        if path_self == prompt_builder.SYSTEM_PROMPT_PATH:
            read_count["value"] += 1
        return original_read_text(path_self, *args, **kwargs)

    prompt_builder._load_system_prompt.cache_clear()
    monkeypatch.setattr(Path, "read_text", counting_read_text)

    prompt_builder.build_case_messages(case)
    prompt_builder.build_case_messages(case)

    assert read_count["value"] == 1


def test_inspect_helper_supports_repeated_expected_tool_args():
    from src.rlvr.inspect_rlvr_training_data import infer_tool_arguments

    case = BenchmarkCase(
        id="par_inspect_args",
        case_type="parallel",
        user_input="同时帮我查 Meta 的广告格式政策和内容限制政策。",
        expected_behavior="tool_call",
        expected_tools=["get_platform_policy", "get_platform_policy"],
        expected_tool_args={
            "get_platform_policy": [
                {"platform": "Meta", "policy_type": "ad_format"},
                {"platform": "Meta", "policy_type": "content_restriction"},
            ]
        },
    )

    assert infer_tool_arguments(case, "get_platform_policy", tool_index=0) == {
        "platform": "Meta",
        "topic": "creative_spec",
        "policy_type": "ad_format",
    }
    assert infer_tool_arguments(case, "get_platform_policy", tool_index=1) == {
        "platform": "Meta",
        "topic": "creative_spec",
        "policy_type": "content_restriction",
    }


def test_inspect_helper_merges_partial_expected_args_with_executable_defaults():
    from src.rlvr.inspect_rlvr_training_data import infer_tool_arguments

    case = BenchmarkCase(
        id="seq_partial_expected_args",
        case_type="sequential",
        user_input="先帮我检查这条素材是否合规，如果没问题再上传到 CMP_1024。",
        context={"platform": "Meta", "campaign_id": "CMP_1024"},
        expected_behavior="tool_call",
        expected_tools=["validate_creative_spec", "upload_creative_asset"],
        expected_tool_args={
            "validate_creative_spec": {"platform": "Meta"},
            "upload_creative_asset": {"campaign_id": "CMP_1024"},
        },
    )

    assert infer_tool_arguments(case, "validate_creative_spec") == {
        "file_path": "assets/mock_video.mp4",
        "platform": "Meta",
        "ad_format": "interstitial",
    }
    assert infer_tool_arguments(case, "upload_creative_asset", tool_index=1) == {
        "file_path": "assets/mock_video.mp4",
        "campaign_id": "CMP_1024",
        "asset_type": "video",
    }
