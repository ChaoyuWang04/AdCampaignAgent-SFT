#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib
import json
import sys
from pathlib import Path


TOOLS_PATH = Path(__file__).resolve().parents[2] / "src" / "tools" / "all_tools.json"
ROOT = TOOLS_PATH.parents[2]

if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

EXPECTED_TOOL_NAMES = [
    "search_trending_creatives",
    "search_competitor_ads",
    "get_trending_hooks",
    "validate_creative_spec",
    "upload_creative_asset",
    "batch_upload_creatives",
    "get_campaign_metrics",
    "get_creative_performance",
    "get_appsflyer_report",
    "compare_campaigns",
    "detect_anomalies",
    "get_optimization_playbook",
    "query_knowledge_base",
    "get_benchmark_data",
    "get_platform_policy",
]


def test_all_tools_json_contains_expected_ad_tools_only():
    payload = json.loads(TOOLS_PATH.read_text(encoding="utf-8"))
    names = [item["function"]["name"] for item in payload]

    assert names == EXPECTED_TOOL_NAMES
    assert "search_travel_guide" not in names
    assert "get_weather_info" not in names
    assert "query_route" not in names
    assert "recommend_hotels" not in names
    assert "get_hotel_reviews" not in names


def test_each_tool_has_its_own_module_and_export():
    for tool_name in EXPECTED_TOOL_NAMES:
        module = importlib.import_module(f"src.tools.{tool_name}")
        assert hasattr(module, tool_name)
        assert callable(getattr(module, tool_name))


def test_tools_package_exports_all_ad_tools():
    tools_pkg = importlib.import_module("src.tools")

    for tool_name in EXPECTED_TOOL_NAMES:
        assert hasattr(tools_pkg, tool_name)
        assert callable(getattr(tools_pkg, tool_name))


def test_non_rag_tool_falls_back_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from src.tools.search_trending_creatives import search_trending_creatives

    result = search_trending_creatives(platform="Meta", game_genre="casual")

    assert isinstance(result, dict)
    assert "results" in result
    assert result["total"] >= 1


def test_rag_tool_falls_back_when_rag_unavailable(monkeypatch):
    monkeypatch.setenv("RAG_API_URL", "http://127.0.0.1:9")

    from src.tools.query_knowledge_base import query_knowledge_base

    result = query_knowledge_base(question="tROAS 和 tCPA 的区别是什么？")

    assert isinstance(result, dict)
    assert result["total"] >= 1
    assert "chunks" in result
