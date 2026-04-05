#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate rule-based RLVR task seeds."""

from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.common.project_paths import data_dir
from src.rlvr.datapipeline.workflow_loader import load_all_workflow_configs


PLATFORMS = ["Google", "Meta", "Tiktok", "Applovin", "Unity"]
GAME_GENRES = ["casual", "puzzle", "hyper_casual", "strategy", "rpg"]
REGIONS = ["US", "JP", "SEA", "KR", "EU"]
COMPETITORS = ["Playrix", "Rollic", "Voodoo", "Jam City", "SciPlay"]
POLICY_TYPES = ["ad_format", "content_restriction", "targeting", "billing"]
ISSUE_TYPES = ["low_roas", "low_ctr", "low_retention", "creative_fatigue", "budget_underdelivery"]


def load_workflow_definitions() -> dict[int, dict[str, Any]]:
    return load_all_workflow_configs()


def flatten_tool_plan(tool_plan: list[dict[str, Any]]) -> list[str]:
    flattened: list[str] = []
    for group in tool_plan:
        flattened.extend(group.get("tools", []))
    return flattened


def has_parallel_group(tool_plan: list[dict[str, Any]]) -> bool:
    return any(group.get("mode") == "parallel" and len(group.get("tools", [])) > 1 for group in tool_plan)


def pick_bucket_by_query_count(intent_buckets: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    names = list(intent_buckets.keys())
    weights = [max(1, len(intent_buckets[name].get("queries", []))) for name in names]
    picked = random.choices(names, weights=weights, k=1)[0]
    return picked, intent_buckets[picked]


def random_context() -> dict[str, Any]:
    platform = random.choice(PLATFORMS)
    genre = random.choice(GAME_GENRES)
    return {
        "platform": platform,
        "game_genre": genre,
        "region": random.choice(REGIONS),
        "campaign_id": f"CMP_{random.randint(1000, 9999)}",
        "campaign_id_alt": f"CMP_{random.randint(1000, 9999)}",
        "app_id": f"com.example.{genre}{random.randint(1, 99):02d}",
        "competitor_name": random.choice(COMPETITORS),
        "policy_type": random.choice(POLICY_TYPES),
        "policy_type_alt": random.choice(POLICY_TYPES),
        "metric": random.choice(["roas", "retention_d1", "ctr", "spend", "cpi"]),
        "issue_type": random.choice(ISSUE_TYPES),
        "date_range": {"start": "2026-03-01", "end": "2026-03-07"},
    }


SLOT_TO_CONTEXT_KEY = {
    "platform": "platform",
    "region": "region",
    "genre": "game_genre",
    "campaign_id": "campaign_id",
    "app_id": "app_id",
}


def _default_output_path() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return data_dir() / "rlvr" / "raw" / f"rlvr_seeds_{ts}.json"


class RLVRSeedGenerator:
    def __init__(self) -> None:
        self.workflow_defs = load_workflow_definitions()

    def _workflow(self, workflow_id: int) -> dict[str, Any]:
        return self.workflow_defs[workflow_id]

    def _format(self, template: str, ctx: dict[str, Any], **extra: Any) -> str:
        values = dict(ctx)
        values.update(
            {
                "genre": ctx["game_genre"],
                "competitor": ctx["competitor_name"],
                **extra,
            }
        )
        return template.format(**values)

    def _base_record(self, workflow_id: int, bucket_name: str, bucket: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": f"{bucket.get('id_prefix', self._workflow(workflow_id)['id_prefix'])}_{random.randint(100000, 999999)}",
            "workflow": workflow_id,
            "workflow_name": self._workflow(workflow_id)["workflow_name"],
            "case_type": self._workflow(workflow_id)["case_type"],
            "user_input": "",
            "context": {
                key: value
                for key, value in ctx.items()
                if key in {"platform", "game_genre", "region", "campaign_id", "campaign_id_alt", "app_id", "date_range"}
            },
            "intent_bucket": bucket_name,
            "scene_tag": bucket.get("scene_tag", bucket_name),
            "expected_behavior": bucket.get("expected_behavior", "tool_call"),
            "tool_plan": bucket.get("tool_plan", []),
            "expected_tool_args": {},
            "required_missing_slots": list(bucket.get("required_slots", [])) if bucket.get("expected_behavior") == "clarify" else [],
            "rejection_category": bucket.get("rejection_category"),
            "rlvr_tags": list(bucket.get("rlvr_tags", [])),
            "rlvr_weight": float(bucket.get("rlvr_weight", 1.0)),
            "rlvr_max_tool_rounds": int(bucket.get("rlvr_max_tool_rounds", self._workflow(workflow_id).get("rlvr_max_tool_rounds", 2))),
        }

    def _sanitize_context_for_missing_slots(self, context: dict[str, Any], required_missing_slots: list[str]) -> dict[str, Any]:
        sanitized = dict(context)
        for slot in required_missing_slots:
            key = SLOT_TO_CONTEXT_KEY.get(slot)
            if key is not None:
                sanitized.pop(key, None)
        return sanitized

    def _build_expected_tool_args(
        self,
        tool_plan: list[dict[str, Any]],
        ctx: dict[str, Any],
        bucket_name: str,
    ) -> dict[str, Any]:
        args_by_tool: dict[str, Any] = {}
        for group in tool_plan:
            group_tools = group.get("tools", [])
            for index, tool_name in enumerate(group_tools):
                tool_args = self._tool_arguments(tool_name, ctx, bucket_name=bucket_name, tool_index=index)
                existing = args_by_tool.get(tool_name)
                if existing is None:
                    args_by_tool[tool_name] = tool_args
                elif isinstance(existing, list):
                    existing.append(tool_args)
                else:
                    args_by_tool[tool_name] = [existing, tool_args]
        return args_by_tool

    def _tool_arguments(self, tool_name: str, ctx: dict[str, Any], *, bucket_name: str, tool_index: int) -> dict[str, Any]:
        if tool_name == "get_campaign_metrics":
            campaign_id = ctx["campaign_id"] if tool_index == 0 else ctx.get("campaign_id_alt", ctx["campaign_id"])
            return {"campaign_id": campaign_id}
        if tool_name == "search_competitor_ads":
            return {
                "competitor_name": ctx["competitor_name"],
                "platform": ctx["platform"],
            }
        if tool_name == "get_benchmark_data":
            return {
                "metric": ctx["metric"],
                "game_genre": ctx["game_genre"],
            }
        if tool_name == "get_platform_policy":
            policy_type = ctx["policy_type"] if tool_index == 0 else ctx.get("policy_type_alt", ctx["policy_type"])
            return {
                "platform": ctx["platform"],
                "policy_type": policy_type,
            }
        if tool_name == "validate_creative_spec":
            return {
                "file_path": f"assets/{ctx['game_genre']}_video_01.mp4",
                "platform": ctx["platform"],
            }
        if tool_name == "upload_creative_asset":
            return {
                "file_path": f"assets/{ctx['game_genre']}_video_01.mp4",
                "campaign_id": ctx["campaign_id"],
            }
        if tool_name == "get_creative_performance":
            return {"campaign_id": ctx["campaign_id"]}
        if tool_name == "get_optimization_playbook":
            return {"issue_type": ctx["issue_type"]}
        if tool_name == "detect_anomalies":
            return {"campaign_id": ctx["campaign_id"]}
        if tool_name == "get_appsflyer_report":
            return {"app_id": ctx["app_id"]}
        if tool_name == "query_knowledge_base":
            return {"question": "UA strategy"}
        return {}

    def _materialize_bucket(self, workflow_id: int, bucket_name: str, bucket: dict[str, Any]) -> dict[str, Any]:
        ctx = random_context()
        if bucket_name == "parallel_policy_dual_lookup":
            ctx["policy_type"] = "ad_format"
            ctx["policy_type_alt"] = "content_restriction"
        elif bucket_name == "policy_lookup":
            ctx["policy_type"] = "content_restriction"
        elif bucket_name == "benchmark_lookup":
            ctx["metric"] = "roas"
        elif bucket_name == "analyze_then_benchmark":
            ctx["metric"] = "roas"
        record = self._base_record(workflow_id, bucket_name, bucket, ctx)
        record["user_input"] = self._format(random.choice(bucket["queries"]), ctx)
        if record["expected_behavior"] == "tool_call":
            record["expected_tool_args"] = self._build_expected_tool_args(record["tool_plan"], ctx, bucket_name)
        elif record["expected_behavior"] == "clarify":
            record["tool_plan"] = []
            record["expected_tool_args"] = {}
            record["context"] = self._sanitize_context_for_missing_slots(
                record["context"],
                record["required_missing_slots"],
            )
        else:
            record["tool_plan"] = []
            record["expected_tool_args"] = {}
        return record

    def _generate_for_workflow(self, workflow_id: int, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(workflow_id)
        intent_buckets = cfg["intent_buckets"]
        return [
            self._materialize_bucket(workflow_id, *pick_bucket_by_query_count(intent_buckets))
            for _ in range(count)
        ]

    def gen_workflow1_standard_tool_call(self, count: int) -> list[dict[str, Any]]:
        return self._generate_for_workflow(1, count)

    def gen_workflow2_sequential_tool_call(self, count: int) -> list[dict[str, Any]]:
        return self._generate_for_workflow(2, count)

    def gen_workflow3_parallel_tool_call(self, count: int) -> list[dict[str, Any]]:
        return self._generate_for_workflow(3, count)

    def gen_workflow4_clarify(self, count: int) -> list[dict[str, Any]]:
        return self._generate_for_workflow(4, count)

    def gen_workflow5_reject(self, count: int) -> list[dict[str, Any]]:
        return self._generate_for_workflow(5, count)

    def generate_records(self) -> list[dict[str, Any]]:
        task_plan = [
            (self.gen_workflow1_standard_tool_call, self._workflow(1)["count"]),
            (self.gen_workflow2_sequential_tool_call, self._workflow(2)["count"]),
            (self.gen_workflow3_parallel_tool_call, self._workflow(3)["count"]),
            (self.gen_workflow4_clarify, self._workflow(4)["count"]),
            (self.gen_workflow5_reject, self._workflow(5)["count"]),
        ]
        records: list[dict[str, Any]] = []
        for generator, count in task_plan:
            records.extend(generator(count))
        random.shuffle(records)
        return records

    def generate(self, output_path: str | Path | None = None) -> list[dict[str, Any]]:
        records = self.generate_records()
        target_path = Path(output_path) if output_path is not None else _default_output_path()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return records


if __name__ == "__main__":
    RLVRSeedGenerator().generate()
