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


def test_workflow4_scene_queries_mostly_ground_date_range():
    workflow = workflow_loader.load_all_workflow_configs()[4]
    time_tokens = [
        "最近",
        "近期",
        "上周",
        "这周",
        "本周",
        "上个月",
        "这个月",
        "近一周",
        "近7天",
        "近30天",
        "最近7天",
        "最近30天",
        "最近三天",
        "最近几天",
        "昨天",
        "今天",
        "这几天",
        "这段时间",
        "月底",
        "月初",
        "两天",
        "三天",
        "不到3天",
        "几天",
        "这期",
        "这一轮",
    ]

    for scene, queries in workflow["scene_query_map"].items():
        grounded = sum(any(token in query for token in time_tokens) for query in queries)
        assert grounded >= 6, f"{scene} should ground date_range in at least 6 templates, got {grounded}"


def test_workflow6_industry_benchmark_queries_mostly_ground_all_required_slots():
    workflow = workflow_loader.load_all_workflow_configs()[6]
    queries = workflow["intent_buckets"]["industry_benchmark"]["queries"]
    platform_tokens = ["Google", "Meta", "TikTok", "Tiktok", "Applovin", "Unity", "UAC", "Facebook"]
    region_tokens = ["US", "JP", "SEA", "KR", "EU"]
    genre_tokens = ["casual", "puzzle", "strategy", "rpg", "hyper-casual", "hyper_casual", "休闲", "RPG"]

    grounded = 0
    for query in queries:
        has_platform = any(token in query for token in platform_tokens)
        has_region = any(token in query for token in region_tokens)
        has_genre = any(token in query for token in genre_tokens)
        if has_platform and has_region and has_genre:
            grounded += 1

    assert grounded >= 12, f"industry_benchmark should ground all slots in at least 12 templates, got {grounded}"


def test_workflow1_trending_creatives_queries_mostly_ground_platform_and_genre():
    workflow = workflow_loader.load_all_workflow_configs()[1]
    queries = workflow["intent_buckets"]["trending_creatives"]["queries"]
    platform_tokens = ["{platform}", "Google", "Meta", "TikTok", "Tiktok", "Applovin", "Unity", "UAC", "Facebook"]
    genre_tokens = ["{genre}", "casual", "puzzle", "strategy", "rpg", "hyper-casual", "hyper_casual", "休闲", "RPG"]

    grounded = 0
    for query in queries:
        has_platform = any(token in query for token in platform_tokens)
        has_genre = any(token in query for token in genre_tokens)
        if has_platform and has_genre:
            grounded += 1

    assert grounded >= 12, f"trending_creatives should ground platform and genre in at least 12 templates, got {grounded}"
