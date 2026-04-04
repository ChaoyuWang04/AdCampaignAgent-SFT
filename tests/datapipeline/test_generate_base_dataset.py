import importlib.util
from pathlib import Path


GENERATOR_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "0_generate_base_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_base_dataset", GENERATOR_PATH)
generate_base_dataset = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generate_base_dataset)


def test_generate_defaults_to_data_raw(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    script_path = repo_root / "src" / "datapipeline" / "0_generate_base_dataset.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test stub\n", encoding="utf-8")

    monkeypatch.setattr(generate_base_dataset.Path, "resolve", lambda self: script_path)

    generator = generate_base_dataset.AdDatasetGenerator()
    records = generator.generate()

    raw_dir = repo_root / "data" / "raw"
    output_files = list(raw_dir.glob("ad_agent_seeds_*_zh.json"))

    assert len(records) == sum(workflow["count"] for workflow in generate_base_dataset.load_workflow_definitions().values())
    assert raw_dir.is_dir()
    assert len(output_files) == 1


def test_generate_record_keeps_seed_contract():
    generator = generate_base_dataset.AdDatasetGenerator()

    record = generator.gen_workflow1_creative_search(1)[0]

    expected_keys = {
        "workflow",
        "workflow_name",
        "user_role",
        "platform",
        "game_genre",
        "region",
        "campaign_id",
        "app_id",
        "date_range",
        "roas_baseline_d7",
        "roas_baseline_d30",
        "ret_baseline_d1",
        "ret_baseline_d7",
        "user_query",
        "needs_clarification",
        "clarification_reason",
        "clarification_answer",
        "scene_tag",
        "tool_plan",
        "tool_chain",
        "has_parallel",
        "refusal_type",
    }

    assert expected_keys.issubset(record.keys())
    assert record["workflow"] == 1
    assert record["workflow_name"] == "素材搜寻"
    assert isinstance(record["tool_plan"], list)
    assert isinstance(record["tool_chain"], list)


def test_workflow_definitions_load_from_yaml():
    workflows = generate_base_dataset.load_workflow_definitions()

    assert set(workflows) == {1, 2, 3, 4, 5, 6, 7}
    assert workflows[1]["workflow_name"] == "素材搜寻"
    assert workflows[1]["count"] == 360
    assert workflows[1]["intent_buckets"]


def test_workflow1_competitor_queries_bind_to_competitor_tool(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()

    monkeypatch.setattr(generate_base_dataset.random, "random", lambda: 0.9)
    monkeypatch.setattr(
        generate_base_dataset,
        "pick_bucket_by_query_count",
        lambda buckets: (
            "competitor_ads",
            {
                "scene_tag": "competitor_ads_search",
                "tool_plan": [{"mode": "serial", "tools": ["search_competitor_ads"]}],
                "queries": ["查一下{competitor}最近在{platform}上投了什么广告"],
            },
        ),
    )

    record = generator.gen_workflow1_creative_search(1)[0]

    assert record["intent_bucket"] == "competitor_ads"
    assert record["tool_chain"] == ["search_competitor_ads"]
    assert record["query_slots"]["competitor_name"] in record["user_query"]


def test_workflow3_appsflyer_queries_bind_to_appsflyer_tool(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()

    monkeypatch.setattr(generate_base_dataset.random, "random", lambda: 0.9)
    monkeypatch.setattr(
        generate_base_dataset,
        "pick_bucket_by_query_count",
        lambda buckets: ("appsflyer_report", buckets["appsflyer_report"]),
    )

    record = generator.gen_workflow3_single_query(1)[0]

    assert record["intent_bucket"] == "appsflyer_report"
    if has_app_id := ("." in record["user_query"] and any(token in record["user_query"] for token in ["com.", "io."])):
        assert record["tool_chain"] == ["get_appsflyer_report"]
        assert record["scene_tag"] == "appsflyer_report"
    else:
        assert record["needs_clarification"] is True
        assert record["tool_chain"] == []
        assert record["clarification_reason"] == "app_id_missing"


def test_workflow3_appsflyer_query_templates_all_ground_app_id():
    generator = generate_base_dataset.AdDatasetGenerator()
    bucket = generator._workflow(3)["intent_buckets"]["appsflyer_report"]
    ctx = generate_base_dataset.random_context()

    for template in bucket["queries"]:
        query = generator._format(template, ctx)
        missing = generate_base_dataset.missing_required_slots(
            query,
            generator._bucket_required_slots(3, "appsflyer_report", bucket),
        )
        assert missing == [], f"appsflyer_report query must ground app_id: {query}"


def test_workflow6_policy_queries_bind_to_policy_tool(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()

    monkeypatch.setattr(
        generate_base_dataset,
        "pick_bucket_by_query_count",
        lambda buckets: ("platform_policy", buckets["platform_policy"]),
    )
    monkeypatch.setattr(
        generate_base_dataset.random,
        "choice",
        lambda items: "Google UAC对游戏广告有哪些内容限制？"
        if "Google UAC对游戏广告有哪些内容限制？" in items
        else items[0],
    )

    record = generator.gen_workflow6_knowledge(1)[0]

    assert record["intent_bucket"] == "platform_policy"
    assert record["tool_chain"] == ["get_platform_policy"]
    assert record["scene_tag"] == "platform_policy"


def test_workflow6_platform_policy_queries_include_clarify_templates():
    generator = generate_base_dataset.AdDatasetGenerator()
    bucket = generator._workflow(6)["intent_buckets"]["platform_policy"]

    missing_distributions = []
    for query_template in bucket["queries"]:
        query = generator._format(query_template, generate_base_dataset.random_context()) if "{" in query_template else query_template
        missing = generate_base_dataset.missing_required_slots(
            query,
            generator._bucket_required_slots(6, "platform_policy", bucket),
        )
        missing_distributions.append(tuple(missing))

    assert () in missing_distributions
    assert ("platform",) in missing_distributions


def test_workflow6_creative_guideline_no_longer_contains_platform_spec_queries():
    generator = generate_base_dataset.AdDatasetGenerator()
    queries = generator._workflow(6)["intent_buckets"]["creative_guideline"]["queries"]

    removed_queries = {
        "Meta Reels 素材尺寸和时长一般怎么要求？",
        "TikTok 视频广告文件大小和比例要求是什么？",
        "Google UAC 视频素材建议准备哪些规格？",
    }

    assert removed_queries.isdisjoint(set(queries))
    assert "playable 广告在不同平台有没有通用的尺寸限制？" in queries


def test_workflow4_retention_scene_binds_to_retention_tool_chain(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()
    generator.workflow_defs[4]["scene_query_map"]["ret_danger"] = ["{campaign_id}最近7天D1和D7留存都很差，帮我全面分析"]

    monkeypatch.setattr(generate_base_dataset.random, "random", lambda: 0.9)
    monkeypatch.setattr(generate_base_dataset.random, "choice", lambda items: "ret_danger" if "ret_danger" in items else items[0])

    record = generator.gen_workflow4_deep_analysis(1)[0]

    assert record["intent_bucket"] == "retention_diagnosis"
    assert record["tool_chain"] == ["get_campaign_metrics", "get_appsflyer_report", "get_creative_performance", "get_benchmark_data"]
    assert record["query_slots"]["benchmark_metric"] == "retention_d1"


def test_workflow5_creative_fatigue_binds_to_creative_diagnosis_chain(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()

    monkeypatch.setattr(generate_base_dataset.random, "choice", lambda items: "creative_fatigue" if "creative_fatigue" in items else items[0])

    record = generator.gen_workflow5_anomaly(1)[0]

    assert record["intent_bucket"] == "creative_fatigue"
    assert record["tool_chain"] == ["detect_anomalies", "get_creative_performance", "get_optimization_playbook"]


def test_workflow5_ret_danger_binds_to_retention_diagnosis_chain(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()

    monkeypatch.setattr(generate_base_dataset.random, "choice", lambda items: "ret_danger" if "ret_danger" in items else items[0])

    record = generator.gen_workflow5_anomaly(1)[0]

    assert record["intent_bucket"] == "ret_danger"
    assert record["tool_plan"] == [{"mode": "serial", "tools": ["detect_anomalies", "get_appsflyer_report", "get_optimization_playbook"]}]
    assert record["tool_chain"] == ["detect_anomalies", "get_appsflyer_report", "get_optimization_playbook"]


def test_workflow7_no_longer_generates_insufficient_data_refusals():
    generator = generate_base_dataset.AdDatasetGenerator()

    records = generator.gen_workflow7_refusal(10)

    assert {record["refusal_type"] for record in records} == {
        "off_topic",
        "unauthorized_internal",
        "unauthorized_external",
    }


def test_workflow1_competitor_query_without_platform_turns_into_clarify(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()

    monkeypatch.setattr(generate_base_dataset.random, "random", lambda: 0.9)
    monkeypatch.setattr(
        generate_base_dataset,
        "pick_bucket_by_query_count",
        lambda buckets: (
            "competitor_ads",
            {
                "required_slots": ["platform"],
                "clarification_reason": "platform_missing",
                "scene_tag": "competitor_ads_search",
                "tool_plan": [{"mode": "serial", "tools": ["search_competitor_ads"]}],
                "queries": ["给我看看{competitor}最近的广告长什么样"],
            },
        ),
    )

    record = generator.gen_workflow1_creative_search(1)[0]

    assert record["needs_clarification"] is True
    assert record["tool_chain"] == []
    assert record["clarification_reason"] == "platform_missing"


def test_workflow6_benchmark_query_without_platform_becomes_clarify(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()

    monkeypatch.setattr(
        generate_base_dataset,
        "pick_bucket_by_query_count",
        lambda buckets: (
            "industry_benchmark",
            {
                "required_slots": ["platform", "region", "genre"],
                "clarification_reason": "platform_region_or_genre_missing",
                "tool_plan": [{"mode": "serial", "tools": ["get_benchmark_data"]}],
                "queries": ["EU 地区 casual 游戏的 D1 留存通常能到多少？"],
            },
        ),
    )

    record = generator.gen_workflow6_knowledge(1)[0]

    assert record["needs_clarification"] is True
    assert record["tool_chain"] == []
    assert record["clarification_reason"] == "platform_region_or_genre_missing"


def test_workflow2_upload_query_without_campaign_id_becomes_clarify(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()
    generator.workflow_defs[2]["intent_buckets"]["batch_upload"]["queries"] = ["帮我批量上传这批素材"]

    monkeypatch.setattr(generate_base_dataset.random, "random", lambda: 0.9)
    monkeypatch.setattr(
        generate_base_dataset,
        "pick_bucket_by_query_count",
        lambda buckets: ("batch_upload", buckets["batch_upload"]),
    )
    monkeypatch.setattr(generate_base_dataset.random, "choice", lambda items: items[0])

    record = generator.gen_workflow2_upload(1)[0]

    assert record["needs_clarification"] is True
    assert record["tool_chain"] == []
    assert record["clarification_reason"] == "campaign_id_missing"


def test_workflow2_validate_retry_queries_do_not_include_platform_placeholder():
    generator = generate_base_dataset.AdDatasetGenerator()

    queries = generator.workflow_defs[2]["intent_buckets"]["validate_only_retry"]["queries"]

    assert all("{platform}" not in query for query in queries)


def test_workflow2_validate_retry_queries_all_express_retry_semantics():
    generator = generate_base_dataset.AdDatasetGenerator()

    queries = generator.workflow_defs[2]["intent_buckets"]["validate_only_retry"]["queries"]
    retry_tokens = ("重新", "重传", "再传", "没过", "失败", "被拒", "打回", "补传", "没收进去", "卡住")

    assert all(any(token in query for token in retry_tokens) for query in queries)


def test_workflow4_query_without_time_scope_becomes_clarify(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()
    generator.workflow_defs[4]["scene_query_map"]["healthy"] = ["请帮我分析一下{campaign_id}的整体表现"]

    monkeypatch.setattr(generate_base_dataset.random, "random", lambda: 0.9)
    monkeypatch.setattr(generate_base_dataset.random, "choice", lambda items: "healthy" if "healthy" in items else items[0])

    record = generator.gen_workflow4_deep_analysis(1)[0]

    assert record["needs_clarification"] is True
    assert record["tool_chain"] == []
    assert record["clarification_reason"] == "timerange_missing"


def test_workflow4_ambiguous_clarify_uses_clarify_scene_tag(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()

    monkeypatch.setattr(generate_base_dataset.random, "random", lambda: 0.0)
    monkeypatch.setattr(
        generate_base_dataset.random,
        "choice",
        lambda items: "roas_danger" if items == generator.workflow_defs[4]["scene_tags"] else items[0],
    )

    record = generator.gen_workflow4_deep_analysis(1)[0]

    assert record["needs_clarification"] is True
    assert record["intent_bucket"] == "clarify_missing_scope"
    assert record["scene_tag"] == "clarify_missing_scope"
    assert record["clarification_reason"] == "campaign_id_and_timerange_missing"


def test_workflow4_clarify_answers_use_context_date_range():
    generator = generate_base_dataset.AdDatasetGenerator()
    ctx = {
        **generate_base_dataset.random_context(),
        "campaign_id": "CMP_1234",
        "date_range": {"start": "2026-02-01", "end": "2026-02-08"},
    }

    assert generator._clarify_answer(generator._workflow(4), "timerange_missing", ctx) == "时间是2026-02-01到2026-02-08"
    assert (
        generator._clarify_answer(generator._workflow(4), "campaign_id_and_timerange_missing", ctx)
        == "看CMP_1234，时间是2026-02-01到2026-02-08"
    )


def test_workflow5_query_without_campaign_id_becomes_clarify(monkeypatch):
    generator = generate_base_dataset.AdDatasetGenerator()
    generator.workflow_defs[5]["scene_query_map"]["roas_danger"] = ["ROAS今天突然跌了很多，帮我诊断"]

    monkeypatch.setattr(generate_base_dataset.random, "choice", lambda items: "roas_danger" if "roas_danger" in items else items[0])

    record = generator.gen_workflow5_anomaly(1)[0]

    assert record["needs_clarification"] is True
    assert record["tool_chain"] == []
    assert record["clarification_reason"] == "campaign_id_missing"
