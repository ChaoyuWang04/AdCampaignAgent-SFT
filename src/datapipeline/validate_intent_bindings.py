from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


WORKFLOW_DIR = Path(__file__).resolve().parent / "workflow"

PLATFORM_TOKENS = ["Google", "Meta", "TikTok", "Tiktok", "Applovin", "Unity", "UAC", "Facebook"]
GENRE_TOKENS = ["casual", "puzzle", "hyper-casual", "hyper_casual", "strategy", "rpg"]
REGION_TOKENS = ["US", "JP", "SEA", "KR", "EU"]

CLARIFY_ONLY_INTENTS: dict[int, set[str]] = {
    1: {"clarify"},
    3: {"clarify_missing_campaign"},
    4: {"clarify_missing_scope"},
}


def load_all_workflow_configs() -> dict[int, dict[str, Any]]:
    configs: dict[int, dict[str, Any]] = {}
    for path in sorted(WORKFLOW_DIR.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        configs[int(payload["workflow_id"])] = payload
    return configs


def flatten_tool_plan(tool_plan: list[dict[str, Any]]) -> set[str]:
    tools: set[str] = set()
    for step in tool_plan:
        for tool in step.get("tools", []):
            tools.add(tool)
    return tools


def build_allowed_tool_sets() -> dict[tuple[int, str], set[str]]:
    allowed: dict[tuple[int, str], set[str]] = {}
    for workflow_id, cfg in load_all_workflow_configs().items():
        intent_buckets = cfg.get("intent_buckets", {})
        if isinstance(intent_buckets, dict):
            for bucket_name, bucket in intent_buckets.items():
                allowed[(workflow_id, bucket_name)] = flatten_tool_plan(bucket.get("tool_plan", []))

        scene_tool_plan_map = cfg.get("scene_tool_plan_map", {})
        scene_intent_map = cfg.get("scene_intent_map", {})
        if isinstance(scene_tool_plan_map, dict):
            for scene, tool_plan in scene_tool_plan_map.items():
                intent = scene_intent_map.get(scene, scene)
                allowed[(workflow_id, intent)] = flatten_tool_plan(tool_plan)

        refusal_templates = cfg.get("refusal_templates", {})
        if isinstance(refusal_templates, dict):
            for refusal_type in refusal_templates:
                allowed[(workflow_id, refusal_type)] = set()

        for clarify_intent in CLARIFY_ONLY_INTENTS.get(workflow_id, set()):
            allowed[(workflow_id, clarify_intent)] = set()
    return allowed


def build_required_slots() -> dict[tuple[int, str], tuple[str, ...]]:
    required: dict[tuple[int, str], tuple[str, ...]] = {}
    for workflow_id, cfg in load_all_workflow_configs().items():
        intent_buckets = cfg.get("intent_buckets", {})
        if isinstance(intent_buckets, dict):
            for bucket_name, bucket in intent_buckets.items():
                slots = bucket.get("required_slots", [])
                required[(workflow_id, bucket_name)] = tuple(slots)

        top_level_required = cfg.get("required_slots", {})
        if isinstance(top_level_required, dict):
            for intent, slots in top_level_required.items():
                required[(workflow_id, intent)] = tuple(slots)
    return required


ALLOWED_TOOL_SETS = build_allowed_tool_sets()
REQUIRED_SLOTS = build_required_slots()


def has_platform_token(query: str) -> bool:
    return any(token in query for token in PLATFORM_TOKENS)


def has_genre_token(query: str) -> bool:
    lowered = query.lower()
    return any(token in lowered for token in GENRE_TOKENS) or "休闲" in query


def has_region_token(query: str) -> bool:
    return any(token in query for token in REGION_TOKENS)


def has_campaign_token(query: str) -> bool:
    return "CMP_" in query


def has_app_token(query: str) -> bool:
    return "." in query and any(token in query for token in ["com.", "io."])


def has_date_range_token(query: str) -> bool:
    return any(
        token in query
        for token in [
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
    )


SLOT_CHECKERS = {
    "platform": has_platform_token,
    "genre": has_genre_token,
    "region": has_region_token,
    "campaign_id": has_campaign_token,
    "app_id": has_app_token,
    "date_range": has_date_range_token,
}


def missing_required_slots(record: dict[str, Any]) -> list[str]:
    key = (record.get("workflow"), record.get("intent_bucket"))
    required = REQUIRED_SLOTS.get(key, ())
    query = str(record.get("user_query", ""))
    return [slot for slot in required if slot in SLOT_CHECKERS and not SLOT_CHECKERS[slot](query)]


def validate_seed_record(record: dict[str, Any]) -> list[str]:
    workflow = record.get("workflow")
    intent_bucket = record.get("intent_bucket")
    tool_chain = record.get("tool_chain", [])
    key = (workflow, intent_bucket)
    needs_clarification = bool(record.get("needs_clarification"))

    errors: list[str] = []
    allowed = ALLOWED_TOOL_SETS.get(key)
    if allowed is None:
        return errors
    missing_slots = missing_required_slots(record)
    if needs_clarification and not tool_chain and missing_slots:
        return errors
    if set(tool_chain) != allowed:
        errors.append(
            f"intent/tool mismatch for workflow={workflow} intent={intent_bucket}: "
            f"expected {sorted(allowed)}, got {sorted(set(tool_chain))}"
        )

    if tool_chain and missing_slots:
        errors.append(
            f"missing required slots for workflow={workflow} intent={intent_bucket}: {sorted(missing_slots)}"
        )

    query = str(record.get("user_query", ""))
    query_slots = record.get("query_slots", {})
    if workflow == 1 and intent_bucket == "competitor_ads":
        competitor = query_slots.get("competitor_name")
        if competitor and competitor not in query:
            errors.append("competitor_name slot is not grounded in user_query")
    if workflow == 3 and intent_bucket == "creative_metrics" and "素材" not in query:
        errors.append("creative_metrics intent should be backed by material-specific query wording")
    if workflow == 7 and record.get("refusal_type") == "insufficient_data_to_answer":
        errors.append("insufficient_data_to_answer should no longer appear in workflow 7")
    return errors


def validate_seed_file(path: str | Path) -> list[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    errors: list[str] = []
    for index, record in enumerate(payload):
        for error in validate_seed_record(record):
            errors.append(f"[{index}] {error}")
    return errors


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate datapipeline intent/tool bindings")
    parser.add_argument("path", type=str, help="Seed JSON path")
    args = parser.parse_args()

    validation_errors = validate_seed_file(args.path)
    if validation_errors:
        for error in validation_errors:
            print(error)
        raise SystemExit(1)
    print("intent bindings valid")
