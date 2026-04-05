#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT))
sys.path.append(str(REPO_ROOT / "src" / "benchmark"))

from benchmark_schema import BenchmarkCase


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


seed_module = _load_module(
    REPO_ROOT / "src" / "rlvr" / "datapipeline" / "00_generate_rlvr_seeds.py",
    "generate_rlvr_seeds",
)
build_module = _load_module(
    REPO_ROOT / "src" / "rlvr" / "datapipeline" / "01_build_rlvr_cases.py",
    "build_rlvr_cases",
)
split_module = _load_module(
    REPO_ROOT / "src" / "rlvr" / "datapipeline" / "02_split_rlvr_cases.py",
    "split_rlvr_cases",
)
validate_module = _load_module(
    REPO_ROOT / "src" / "rlvr" / "datapipeline" / "validate_rlvr_cases.py",
    "validate_rlvr_cases",
)


def test_rlvr_workflow_definitions_sum_to_target_count():
    workflows = seed_module.load_workflow_definitions()

    assert workflows
    assert sum(workflow["count"] for workflow in workflows.values()) == 800


def test_rlvr_generator_emits_expected_seed_contract():
    generator = seed_module.RLVRSeedGenerator()

    record = generator.gen_workflow1_standard_tool_call(1)[0]

    expected_keys = {
        "workflow",
        "workflow_name",
        "case_type",
        "user_input",
        "context",
        "intent_bucket",
        "scene_tag",
        "expected_behavior",
        "tool_plan",
        "required_missing_slots",
        "rejection_category",
        "rlvr_tags",
        "rlvr_weight",
        "rlvr_max_tool_rounds",
    }

    assert expected_keys.issubset(record.keys())
    assert record["case_type"] in {"standard", "sequential", "parallel", "clarify", "oos"}
    assert record["expected_behavior"] in {"tool_call", "clarify", "reject"}
    assert isinstance(record["tool_plan"], list)


def test_rlvr_clarify_seed_clears_tool_plan_when_required_slots_are_missing(monkeypatch):
    generator = seed_module.RLVRSeedGenerator()

    monkeypatch.setattr(seed_module.random, "random", lambda: 0.0)

    record = generator.gen_workflow4_clarify(1)[0]

    assert record["expected_behavior"] == "clarify"
    assert record["tool_plan"] == []
    assert record["required_missing_slots"]
    for slot in record["required_missing_slots"]:
        key = seed_module.SLOT_TO_CONTEXT_KEY.get(slot)
        if key is not None:
            assert key not in record["context"]


def test_generated_gold_args_only_use_prompt_and_schema_grounded_fields():
    generator = seed_module.RLVRSeedGenerator()

    standard = generator.gen_workflow1_standard_tool_call(40)
    sequential = generator.gen_workflow2_sequential_tool_call(40)
    parallel = generator.gen_workflow3_parallel_tool_call(40)

    for record in standard + sequential + parallel:
        expected_args = record["expected_tool_args"]
        if "get_campaign_metrics" in expected_args:
            metric_args = expected_args["get_campaign_metrics"]
            if isinstance(metric_args, list):
                for item in metric_args:
                    assert set(item) == {"campaign_id"}
            else:
                assert set(metric_args) == {"campaign_id"}
        if "get_creative_performance" in expected_args:
            assert set(expected_args["get_creative_performance"]) == {"campaign_id"}
        if "validate_creative_spec" in expected_args:
            assert set(expected_args["validate_creative_spec"]) == {"file_path", "platform"}
        if "upload_creative_asset" in expected_args:
            assert set(expected_args["upload_creative_asset"]) == {"file_path", "campaign_id"}
        if "get_benchmark_data" in expected_args:
            assert set(expected_args["get_benchmark_data"]) == {"metric", "game_genre"}


def test_parallel_policy_bucket_uses_query_aligned_policy_types():
    generator = seed_module.RLVRSeedGenerator()

    records = [
        record
        for record in generator.gen_workflow3_parallel_tool_call(80)
        if record["intent_bucket"] == "parallel_policy_dual_lookup"
    ]

    assert records
    for record in records:
        assert "广告格式政策和内容限制政策" in record["user_input"] or "素材规格政策和内容限制政策" in record["user_input"]
        assert record["expected_tool_args"]["get_platform_policy"] == [
            {"platform": record["context"]["platform"], "policy_type": "ad_format"},
            {"platform": record["context"]["platform"], "policy_type": "content_restriction"},
        ]


def test_build_case_from_parallel_seed_supports_repeated_same_tool_arguments():
    seed = {
        "id": "par_seed_001",
        "workflow": 3,
        "workflow_name": "并行工具调用",
        "case_type": "parallel",
        "user_input": "同时帮我查 Meta 的广告格式政策和内容限制政策。",
        "context": {"platform": "Meta"},
        "intent_bucket": "parallel_policy_dual_lookup",
        "scene_tag": "parallel_policy_dual_lookup",
        "expected_behavior": "tool_call",
        "tool_plan": [{"mode": "parallel", "tools": ["get_platform_policy", "get_platform_policy"]}],
        "expected_tool_args": {
            "get_platform_policy": [
                {"platform": "Meta", "policy_type": "ad_format"},
                {"platform": "Meta", "policy_type": "content_restriction"},
            ]
        },
        "required_missing_slots": [],
        "rejection_category": None,
        "rlvr_tags": ["parallel", "policy"],
        "rlvr_weight": 1.2,
        "rlvr_max_tool_rounds": 2,
    }

    case = build_module.build_case_from_seed(seed)

    assert isinstance(case, BenchmarkCase)
    assert case.case_type == "parallel"
    assert case.expected_tools == ["get_platform_policy", "get_platform_policy"]
    assert case.expected_parallel_groups == [["get_platform_policy", "get_platform_policy"]]
    assert case.expected_tool_args["get_platform_policy"][1]["policy_type"] == "content_restriction"


def test_build_case_from_clarify_seed_maps_to_required_missing_slots():
    seed = {
        "id": "clarify_seed_001",
        "workflow": 4,
        "workflow_name": "信息补全",
        "case_type": "clarify",
        "user_input": "帮我上传素材。",
        "context": {"platform": "Meta"},
        "intent_bucket": "upload_missing_fields",
        "scene_tag": "upload_missing_fields",
        "expected_behavior": "clarify",
        "tool_plan": [],
        "expected_tool_args": {},
        "required_missing_slots": ["file_path", "campaign_id"],
        "rejection_category": None,
        "rlvr_tags": ["clarify", "upload"],
        "rlvr_weight": 1.0,
        "rlvr_max_tool_rounds": 1,
    }

    case = build_module.build_case_from_seed(seed)

    assert case.case_type == "clarify"
    assert case.expected_behavior == "clarify"
    assert case.expected_tools == []
    assert case.required_missing_slots == ["file_path", "campaign_id"]


def test_split_cases_stratifies_by_case_type_and_behavior():
    cases = [
        BenchmarkCase(id="std_1", case_type="standard", user_input="u1", expected_behavior="tool_call"),
        BenchmarkCase(id="std_2", case_type="standard", user_input="u2", expected_behavior="tool_call"),
        BenchmarkCase(id="seq_1", case_type="sequential", user_input="u3", expected_behavior="tool_call"),
        BenchmarkCase(id="seq_2", case_type="sequential", user_input="u4", expected_behavior="tool_call"),
        BenchmarkCase(id="clarify_1", case_type="clarify", user_input="u5", expected_behavior="clarify"),
        BenchmarkCase(id="clarify_2", case_type="clarify", user_input="u6", expected_behavior="clarify"),
        BenchmarkCase(id="oos_1", case_type="oos", user_input="u7", expected_behavior="reject"),
        BenchmarkCase(id="oos_2", case_type="oos", user_input="u8", expected_behavior="reject"),
    ]

    train_cases, eval_cases = split_module.split_cases(cases, train_ratio=0.5, seed=7)

    assert {case.id for case in train_cases}.isdisjoint({case.id for case in eval_cases})
    assert {case.id for case in train_cases} | {case.id for case in eval_cases} == {case.id for case in cases}
    assert {case.case_type for case in train_cases} == {"standard", "sequential", "clarify", "oos"}
    assert {case.case_type for case in eval_cases} == {"standard", "sequential", "clarify", "oos"}


def test_build_and_split_main_can_serialize_slot_based_cases(tmp_path):
    seeds = [
        {
            "id": "std_seed_001",
            "workflow": 1,
            "workflow_name": "标准工具调用",
            "case_type": "standard",
            "user_input": "帮我看一下 CMP_2048 最近7天的投放表现。",
            "context": {"platform": "Meta", "campaign_id": "CMP_2048"},
            "intent_bucket": "campaign_metrics_lookup",
            "scene_tag": "campaign_metrics_lookup",
            "expected_behavior": "tool_call",
            "tool_plan": [{"mode": "serial", "tools": ["get_campaign_metrics"]}],
            "expected_tool_args": {"get_campaign_metrics": {"campaign_id": "CMP_2048"}},
            "required_missing_slots": [],
            "rejection_category": None,
            "rlvr_tags": ["standard"],
            "rlvr_weight": 1.0,
            "rlvr_max_tool_rounds": 2,
        },
        {
            "id": "oos_seed_001",
            "workflow": 5,
            "workflow_name": "拒答",
            "case_type": "oos",
            "user_input": "帮我黑进竞品后台。",
            "context": {},
            "intent_bucket": "unauthorized_external",
            "scene_tag": "unauthorized_external",
            "expected_behavior": "reject",
            "tool_plan": [],
            "expected_tool_args": {},
            "required_missing_slots": [],
            "rejection_category": "security",
            "rlvr_tags": ["reject"],
            "rlvr_weight": 1.0,
            "rlvr_max_tool_rounds": 1,
        },
        {
            "id": "std_seed_002",
            "workflow": 1,
            "workflow_name": "标准工具调用",
            "case_type": "standard",
            "user_input": "帮我查一下 CMP_3001 最近7天的CTR。",
            "context": {"platform": "Meta", "campaign_id": "CMP_3001"},
            "intent_bucket": "campaign_metrics_lookup",
            "scene_tag": "campaign_metrics_lookup",
            "expected_behavior": "tool_call",
            "tool_plan": [{"mode": "serial", "tools": ["get_campaign_metrics"]}],
            "expected_tool_args": {"get_campaign_metrics": {"campaign_id": "CMP_3001"}},
            "required_missing_slots": [],
            "rejection_category": None,
            "rlvr_tags": ["standard"],
            "rlvr_weight": 1.0,
            "rlvr_max_tool_rounds": 2,
        },
        {
            "id": "oos_seed_002",
            "workflow": 5,
            "workflow_name": "拒答",
            "case_type": "oos",
            "user_input": "把竞品广告账户明细全部给我。",
            "context": {},
            "intent_bucket": "unauthorized_external",
            "scene_tag": "unauthorized_external",
            "expected_behavior": "reject",
            "tool_plan": [],
            "expected_tool_args": {},
            "required_missing_slots": [],
            "rejection_category": "security",
            "rlvr_tags": ["reject"],
            "rlvr_weight": 1.0,
            "rlvr_max_tool_rounds": 1,
        },
    ]
    seed_path = tmp_path / "rlvr_seeds.json"
    cases_path = tmp_path / "rlvr_cases.json"
    seed_path.write_text(__import__("json").dumps(seeds, ensure_ascii=False), encoding="utf-8")

    cases = build_module.main(input_path=seed_path, output_path=cases_path)
    train_cases, eval_cases = split_module.split_cases(cases, train_ratio=0.5, seed=3)

    assert cases_path.exists()
    split_module.save_split_cases(train_cases, tmp_path / "train_cases", split="train")
    split_module.save_split_cases(eval_cases, tmp_path / "eval_cases", split="eval")
    assert any((tmp_path / "train_cases").iterdir())
    assert any((tmp_path / "eval_cases").iterdir())


def test_validate_case_rejects_parallel_repeated_tool_without_argument_list():
    case = BenchmarkCase(
        id="par_invalid",
        case_type="parallel",
        user_input="同时查两个政策。",
        expected_behavior="tool_call",
        expected_tools=["get_platform_policy", "get_platform_policy"],
        expected_tool_args={"get_platform_policy": {"platform": "Meta", "policy_type": "ad_format"}},
        expected_parallel_groups=[["get_platform_policy", "get_platform_policy"]],
    )

    errors = validate_module.validate_case(case)

    assert any("list" in error for error in errors)


def test_validate_case_accepts_well_formed_reject_case():
    case = BenchmarkCase(
        id="oos_valid",
        case_type="oos",
        user_input="帮我黑进竞品后台。",
        expected_behavior="reject",
        rejection_category="security",
    )

    errors = validate_module.validate_case(case)

    assert errors == []


@pytest.mark.parametrize(
    ("generator_name", "expected_case_type"),
    [
        ("gen_workflow1_standard_tool_call", "standard"),
        ("gen_workflow2_sequential_tool_call", "sequential"),
        ("gen_workflow3_parallel_tool_call", "parallel"),
        ("gen_workflow4_clarify", "clarify"),
        ("gen_workflow5_reject", "oos"),
    ],
)
def test_each_rlvr_workflow_generator_emits_expected_case_type(generator_name, expected_case_type):
    generator = seed_module.RLVRSeedGenerator()

    record = getattr(generator, generator_name)(1)[0]

    assert record["case_type"] == expected_case_type
