import importlib.util
from pathlib import Path


LOADER_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "workflow_loader.py"
SPEC = importlib.util.spec_from_file_location("workflow_loader", LOADER_PATH)
workflow_loader = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(workflow_loader)


def test_load_all_workflow_configs_returns_seven_workflows():
    workflows = workflow_loader.load_all_workflow_configs()

    assert len(workflows) == 7
    assert set(workflows) == {1, 2, 3, 4, 5, 6, 7}


def test_workflow_config_contains_required_fields():
    workflow = workflow_loader.load_all_workflow_configs()[4]

    assert workflow["workflow_id"] == 4
    assert workflow["workflow_name"] == "多维深度分析"
    assert workflow["count"] == 900
    assert isinstance(workflow["scene_tool_plan_map"], dict)
    assert workflow["scene_intent_map"]["ret_warning"] == "retention_diagnosis"


def test_workflow_config_contains_required_slots_mapping():
    workflow = workflow_loader.load_all_workflow_configs()[4]

    assert "required_slots" in workflow
    assert workflow["required_slots"]["holistic_campaign_analysis"] == ["campaign_id", "date_range"]
    assert workflow["required_slots"]["combined_diagnosis"] == ["campaign_id", "date_range"]


def test_bucket_workflow_uses_bucket_level_required_slots_only():
    workflow = workflow_loader.load_all_workflow_configs()[1]

    assert "intent_buckets" in workflow
    assert "required_slots" not in workflow
    assert workflow["intent_buckets"]["competitor_ads"]["required_slots"] == ["platform"]
    assert workflow["intent_buckets"]["competitor_ads"]["clarification_reason"] == "platform_missing"


def test_workflow6_platform_policy_declares_platform_clarify_slots():
    workflow = workflow_loader.load_all_workflow_configs()[6]
    bucket = workflow["intent_buckets"]["platform_policy"]

    assert bucket["required_slots"] == ["platform"]
    assert bucket["clarification_reason"] == "platform_missing"
