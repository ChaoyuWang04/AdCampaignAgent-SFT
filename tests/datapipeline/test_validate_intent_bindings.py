import importlib.util
from pathlib import Path


VALIDATOR_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "validate_intent_bindings.py"
SPEC = importlib.util.spec_from_file_location("validate_intent_bindings", VALIDATOR_PATH)
validate_intent_bindings = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_intent_bindings)
validate_seed_record = validate_intent_bindings.validate_seed_record


def test_validate_seed_record_accepts_matching_intent_tool_pair() -> None:
    record = {
        "workflow": 1,
        "intent_bucket": "competitor_ads",
        "tool_chain": ["search_competitor_ads"],
        "user_query": "查一下Playrix最近在Meta上投了什么广告",
        "query_slots": {"competitor_name": "Playrix"},
    }

    assert validate_seed_record(record) == []


def test_validate_seed_record_rejects_mismatched_tool_pair() -> None:
    record = {
        "workflow": 1,
        "intent_bucket": "competitor_ads",
        "tool_chain": ["search_trending_creatives"],
        "user_query": "查一下Playrix最近在Meta上投了什么广告",
        "query_slots": {"competitor_name": "Playrix"},
    }

    errors = validate_seed_record(record)

    assert errors
    assert "intent/tool mismatch" in errors[0]


def test_validate_seed_record_rejects_removed_refusal_type() -> None:
    record = {
        "workflow": 7,
        "intent_bucket": "off_topic",
        "refusal_type": "insufficient_data_to_answer",
        "tool_chain": [],
        "user_query": "我们最近表现怎么样？",
    }

    errors = validate_seed_record(record)

    assert errors
    assert "should no longer appear" in errors[0]


def test_validate_seed_record_rejects_tool_call_when_campaign_id_missing() -> None:
    record = {
        "workflow": 2,
        "intent_bucket": "batch_upload",
        "tool_chain": ["validate_creative_spec", "batch_upload_creatives"],
        "user_query": "帮我批量上传这批素材",
    }

    errors = validate_seed_record(record)

    assert errors
    assert "missing required slots" in errors[0]


def test_validate_seed_record_rejects_benchmark_call_when_region_missing() -> None:
    record = {
        "workflow": 6,
        "intent_bucket": "industry_benchmark",
        "tool_chain": ["get_benchmark_data"],
        "user_query": "Meta上casual游戏的D7 ROAS基准是多少？",
    }

    errors = validate_seed_record(record)

    assert errors
    assert "missing required slots" in errors[0]


def test_validate_seed_record_accepts_clarify_record_with_empty_tool_chain() -> None:
    record = {
        "workflow": 6,
        "intent_bucket": "industry_benchmark",
        "tool_chain": [],
        "needs_clarification": True,
        "user_query": "Meta上casual游戏的D7 ROAS基准是多少？",
    }

    assert validate_seed_record(record) == []


def test_validator_derives_workflow4_allowed_tools_from_yaml_scene_mapping() -> None:
    allowed = validate_intent_bindings.ALLOWED_TOOL_SETS[(4, "retention_diagnosis")]

    assert allowed == {
        "get_appsflyer_report",
        "get_campaign_metrics",
        "get_benchmark_data",
        "get_creative_performance",
    }


def test_validator_derives_workflow1_required_slots_from_bucket_yaml() -> None:
    required = validate_intent_bindings.REQUIRED_SLOTS[(1, "competitor_ads")]

    assert required == ("platform",)
