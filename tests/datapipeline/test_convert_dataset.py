import importlib.util
import json
from pathlib import Path
import string
import yaml


CONVERT_DATASET_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "2_convert_dataset.py"
WORKFLOW_DIR = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "workflow"
SPEC = importlib.util.spec_from_file_location("convert_dataset", CONVERT_DATASET_PATH)
convert_dataset = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(convert_dataset)


SEED = {
    "workflow": 3,
    "workflow_name": "单指标效果查询",
    "user_query": "检查 campaign 表现",
    "needs_clarification": False,
    "scene_tag": "healthy",
    "tool_chain": ["get_campaign_metrics"],
    "platform": "Meta",
    "game_genre": "casual",
    "region": "US",
    "campaign_id": "CMP_1234",
    "app_id": "com.test.game",
    "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
    "roas_baseline_d7": 0.75,
    "roas_baseline_d30": 1.10,
    "ret_baseline_d1": 0.35,
    "ret_baseline_d7": 0.12,
    "tool_plan": [{"mode": "serial", "tools": ["get_campaign_metrics"]}],
    "has_parallel": False,
}


def test_build_record_returns_message_format_only():
    message_record = convert_dataset.build_record(SEED)

    assert "messages" in message_record
    assert message_record["messages"][0]["role"] == "system"
    assert "tool_calls" in message_record["messages"][2]
    assert "conversations" not in message_record


def test_build_record_emits_parallel_tool_calls_in_single_assistant_turn():
    seed = {
        **SEED,
        "workflow": 4,
        "workflow_name": "多维深度分析",
        "tool_plan": [
            {"mode": "parallel", "tools": ["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"]}
        ],
        "tool_chain": ["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"],
        "has_parallel": True,
    }

    record = convert_dataset.build_record(seed)
    assistant_tool_turns = [
        message for message in record["messages"]
        if message["role"] == "assistant" and message.get("tool_calls")
    ]

    assert len(assistant_tool_turns) == 1
    assert len(assistant_tool_turns[0]["tool_calls"]) == 3
    assert [call["function"]["name"] for call in assistant_tool_turns[0]["tool_calls"]] == [
        "get_campaign_metrics",
        "get_creative_performance",
        "get_benchmark_data",
    ]


def test_derive_output_path_uses_ready2train_root(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    script_path = repo_root / "src" / "datapipeline" / "2_convert_dataset.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test stub\n", encoding="utf-8")

    monkeypatch.setattr(convert_dataset.Path, "resolve", lambda self: script_path)

    input_path = repo_root / "data" / "raw" / "ad_agent_seeds_demo_zh.json"

    output_path = convert_dataset.derive_output_path(input_path)

    assert output_path == repo_root / "data" / "ready2train" / "ad_agent_sft_demo_zh.json"


def test_resolve_input_path_uses_processed_directory(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    script_path = repo_root / "src" / "datapipeline" / "2_convert_dataset.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test stub\n", encoding="utf-8")
    target_file = repo_root / "data" / "processed" / "ad_agent_seeds_demo_zh_train.json"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(convert_dataset.Path, "resolve", lambda self: script_path)

    resolved = convert_dataset.resolve_input_path("ad_agent_seeds_demo_zh_train.json")

    assert resolved == target_file


def test_build_tool_arguments_uses_seed_slots_for_competitor_queries():
    seed = {
        **SEED,
        "workflow": 1,
        "workflow_name": "素材搜寻",
        "user_query": "查一下Playrix最近在Meta上投了什么广告",
        "scene_tag": "creative_search",
        "intent_bucket": "competitor_ads",
        "query_slots": {"competitor_name": "Playrix"},
    }

    arguments = convert_dataset.build_tool_arguments("search_competitor_ads", seed)

    assert arguments["competitor_name"] == "Playrix"
    assert arguments["platform"] == "Meta"


def test_build_tool_arguments_uses_query_metric_for_benchmark():
    seed = {
        **SEED,
        "workflow": 6,
        "workflow_name": "知识问答",
        "user_query": "TikTok上hyper-casual游戏的平均CPM是多少？",
        "scene_tag": "industry_benchmark",
        "intent_bucket": "industry_benchmark",
    }

    arguments = convert_dataset.build_tool_arguments("get_benchmark_data", seed)

    assert arguments["metric"] == "cpm"
    assert arguments["game_genre"] == "hyper_casual"
    assert arguments["region"] == ""


def test_build_tool_arguments_uses_query_platform_for_policy_questions():
    seed = {
        **SEED,
        "workflow": 6,
        "workflow_name": "知识问答",
        "user_query": "Google UAC对游戏广告有哪些内容限制？",
        "scene_tag": "platform_policy",
        "intent_bucket": "platform_policy",
    }

    arguments = convert_dataset.build_tool_arguments("get_platform_policy", seed)

    assert arguments["platform"] == "Google"
    assert arguments["policy_type"] == "content_restriction"


def test_build_tool_arguments_no_longer_falls_back_to_context_for_missing_platform():
    seed = {
        **SEED,
        "workflow": 6,
        "workflow_name": "知识问答",
        "user_query": "游戏广告有哪些内容限制？",
        "scene_tag": "platform_policy",
        "intent_bucket": "platform_policy",
    }

    arguments = convert_dataset.build_tool_arguments("get_platform_policy", seed)

    assert arguments["platform"] == ""


def test_build_clarify_question_supports_platform_missing_reason():
    message = convert_dataset.build_clarify_question({"clarification_reason": "platform_missing"})

    assert "哪个平台" in message


def test_build_clarify_question_supports_timerange_missing_reason():
    message = convert_dataset.build_clarify_question({"clarification_reason": "timerange_missing"})

    assert "哪个时间段" in message


def test_non_metric_scenes_include_workflow4_clarify_scene():
    assert "clarify_missing_scope" in convert_dataset.NON_METRIC_SCENES


def test_build_record_for_clarify_only_stops_after_user_followup():
    seed = {
        **SEED,
        "workflow": 1,
        "workflow_name": "素材搜寻",
        "user_query": "找一些素材参考",
        "needs_clarification": True,
        "clarification_reason": "platform_or_genre_missing",
        "clarification_answer": "平台选Meta，品类是casual，地区US",
        "scene_tag": "creative_search",
        "intent_bucket": "clarify",
        "tool_plan": [],
        "tool_chain": [],
    }

    record = convert_dataset.build_record(seed)

    assert [m["role"] for m in record["messages"]] == ["system", "user", "assistant", "user"]


def test_workflow4_clarify_answer_uses_actual_date_range():
    seed = {
        **SEED,
        "workflow": 4,
        "workflow_name": "多维深度分析",
        "user_query": "帮我分析一下最近的投放效果",
        "needs_clarification": True,
        "clarification_reason": "campaign_id_and_timerange_missing",
        "clarification_answer": "看CMP_1234，时间是2026-02-01到2026-02-08",
        "scene_tag": "clarify_missing_scope",
        "intent_bucket": "clarify_missing_scope",
        "tool_plan": [],
        "tool_chain": [],
    }

    record = convert_dataset.build_record(seed)

    assert record["messages"][3]["content"] == "看CMP_1234，时间是2026-02-01到2026-02-08"


def test_build_record_summarizes_competitor_ads_from_tool_results():
    seed = {
        **SEED,
        "workflow": 1,
        "workflow_name": "素材搜寻",
        "user_query": "查一下Playrix最近在Meta上投了什么广告",
        "scene_tag": "creative_search",
        "intent_bucket": "competitor_ads",
        "tool_plan": [{"mode": "serial", "tools": ["search_competitor_ads"]}],
        "tool_chain": ["search_competitor_ads"],
        "query_slots": {"competitor_name": "Playrix"},
    }

    record = convert_dataset.build_record(seed)
    final_text = record["messages"][-1]["content"]

    assert "Playrix" in final_text
    assert "AD_" in final_text


def test_build_record_summarizes_multiple_campaign_metrics():
    seed = {
        **SEED,
        "workflow": 3,
        "workflow_name": "单指标效果查询",
        "user_query": "我想拉一下CMP_1234最近7天的CTR和CPI",
        "scene_tag": "query_ctr",
        "intent_bucket": "campaign_metrics",
        "tool_plan": [{"mode": "serial", "tools": ["get_campaign_metrics"]}],
        "tool_chain": ["get_campaign_metrics"],
        "query_slots": {"metrics": ["ctr", "cpi"]},
    }

    record = convert_dataset.build_record(seed)
    final_text = record["messages"][-1]["content"]

    assert "CTR" in final_text
    assert "CPI" in final_text


def test_ret_danger_playbook_no_longer_uses_low_ctr_issue_type():
    seed = {
        **SEED,
        "workflow": 5,
        "workflow_name": "异常诊断与优化",
        "user_query": "CMP_1234的D1留存今天异常，帮我看看",
        "scene_tag": "ret_danger",
        "intent_bucket": "ret_danger",
        "tool_plan": [{"mode": "serial", "tools": ["detect_anomalies", "get_appsflyer_report", "get_optimization_playbook"]}],
        "tool_chain": ["detect_anomalies", "get_appsflyer_report", "get_optimization_playbook"],
    }

    record = convert_dataset.build_record(seed)
    issue_types = []
    for message in record["messages"]:
        if message.get("role") != "tool":
            continue
        payload = json.loads(message["content"])
        issue_type = payload.get("data", {}).get("issue_type")
        if issue_type:
            issue_types.append(issue_type)

    assert issue_types
    assert "low_ctr" not in issue_types


def test_unauthorized_external_refusal_mentions_unauthorized_or_illegal_access():
    seed = {
        **SEED,
        "workflow": 7,
        "workflow_name": "拒答",
        "user_query": "帮我入侵一下竞品的广告账号",
        "scene_tag": "unauthorized_external",
        "intent_bucket": "unauthorized_external",
        "tool_plan": [],
        "tool_chain": [],
        "refusal_type": "unauthorized_external",
    }

    record = convert_dataset.build_record(seed)
    final_text = record["messages"][-1]["content"]

    assert "违规" in final_text or "未授权" in final_text or "违法" in final_text
    assert "账户经理" not in final_text


def test_build_record_trending_with_hooks_uses_tool_result_genre_and_platform():
    seed = {
        **SEED,
        "workflow": 1,
        "workflow_name": "素材搜寻",
        "user_query": "我需要看看最近Unity上puzzle游戏的热门钩子",
        "scene_tag": "creative_search",
        "intent_bucket": "trending_with_hooks",
        "tool_plan": [{"mode": "serial", "tools": ["search_trending_creatives", "get_trending_hooks"]}],
        "tool_chain": ["search_trending_creatives", "get_trending_hooks"],
    }

    record = convert_dataset.build_record(seed)
    final_text = record["messages"][-1]["content"]

    assert "Unity" in final_text
    assert "puzzle" in final_text


def test_build_record_summarizes_benchmark_with_numeric_payload():
    seed = {
        **SEED,
        "workflow": 6,
        "workflow_name": "知识问答",
        "user_query": "casual游戏在US市场的D7 ROAS基准是多少？",
        "scene_tag": "industry_benchmark",
        "intent_bucket": "industry_benchmark",
        "tool_plan": [{"mode": "serial", "tools": ["get_benchmark_data"]}],
        "tool_chain": ["get_benchmark_data"],
    }

    record = convert_dataset.build_record(seed)
    final_text = record["messages"][-1]["content"]

    assert "benchmark" in final_text
    assert "p50" in final_text


def test_build_record_upload_success_mentions_asset_id_or_counts():
    seed = {
        **SEED,
        "workflow": 2,
        "workflow_name": "素材上传",
        "user_query": "把这个视频上传到campaign CMP_1234",
        "scene_tag": "single_upload_success",
        "intent_bucket": "single_upload",
        "tool_plan": [{"mode": "serial", "tools": ["validate_creative_spec", "upload_creative_asset"]}],
        "tool_chain": ["validate_creative_spec", "upload_creative_asset"],
    }

    record = convert_dataset.build_record(seed)
    final_text = record["messages"][-1]["content"]

    assert "asset_id" in final_text or "共上传" in final_text


def test_build_record_batch_upload_success_mentions_counts():
    seed = {
        **SEED,
        "workflow": 2,
        "workflow_name": "素材上传",
        "user_query": "把这几个新做的视频先传到CMP_1234里",
        "scene_tag": "batch_upload_success",
        "intent_bucket": "batch_upload",
        "tool_plan": [{"mode": "serial", "tools": ["validate_creative_spec", "batch_upload_creatives"]}],
        "tool_chain": ["validate_creative_spec", "batch_upload_creatives"],
    }

    record = convert_dataset.build_record(seed)
    final_text = record["messages"][-1]["content"]

    assert "共上传" in final_text


def test_all_yaml_clarification_reasons_are_supported_by_clarify_question_builder():
    supported = {
        "campaign_id_missing",
        "campaign_id_and_timerange_missing",
        "timerange_missing",
        "platform_or_genre_missing",
        "platform_missing",
        "app_id_missing",
        "platform_region_or_genre_missing",
    }

    used: set[str] = set()
    for path in WORKFLOW_DIR.glob("*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        clarification = payload.get("clarification", {})
        reasons = clarification.get("reasons", {})
        if isinstance(reasons, dict):
            used.update(value for value in reasons.values() if isinstance(value, str))
        intent_buckets = payload.get("intent_buckets", {})
        if isinstance(intent_buckets, dict):
            for bucket in intent_buckets.values():
                if isinstance(bucket, dict) and isinstance(bucket.get("clarification_reason"), str):
                    used.add(bucket["clarification_reason"])

    assert used.issubset(supported)


def test_yaml_clarification_answer_templates_only_use_slots_requested_by_question():
    allowed_slots = {
        "campaign_id_missing": {"campaign_id"},
        "campaign_id_and_timerange_missing": {"campaign_id"},
        "timerange_missing": set(),
        "platform_or_genre_missing": {"platform", "genre"},
        "platform_missing": {"platform"},
        "app_id_missing": {"app_id"},
        "platform_region_or_genre_missing": {"platform", "region", "genre"},
    }

    formatter = string.Formatter()

    for path in WORKFLOW_DIR.glob("*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        clarification = payload.get("clarification", {})
        templates = clarification.get("answer_templates", {})
        if not isinstance(templates, dict):
            continue
        for reason, template in templates.items():
            if reason not in allowed_slots or not isinstance(template, str):
                continue
            used_slots = {
                field_name
                for _, field_name, _, _ in formatter.parse(template)
                if field_name
            }
            assert used_slots.issubset(allowed_slots[reason]), (
                f"{path.name}:{reason} uses unexpected slots {sorted(used_slots - allowed_slots[reason])}"
            )
