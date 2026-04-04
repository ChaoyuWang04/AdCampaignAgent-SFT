from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


WORKFLOW_DIR = Path(__file__).resolve().parent / "workflow"
REQUIRED_FIELDS = {"workflow_id", "workflow_name", "count"}


def workflow_dir() -> Path:
    return WORKFLOW_DIR


def load_workflow_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"Workflow config must be a mapping: {config_path}")

    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        raise ValueError(f"Workflow config missing required fields {sorted(missing)}: {config_path}")

    if "tool_plans" in payload and not isinstance(payload["tool_plans"], list):
        raise ValueError(f"tool_plans must be a list: {config_path}")
    if "required_slots" in payload:
        required_slots = payload["required_slots"]
        if not isinstance(required_slots, dict):
            raise ValueError(f"required_slots must be a mapping: {config_path}")
        for bucket, slots in required_slots.items():
            if not isinstance(bucket, str) or not isinstance(slots, list) or not all(isinstance(slot, str) for slot in slots):
                raise ValueError(f"required_slots must map strings to string lists: {config_path}")
    if "intent_buckets" in payload:
        intent_buckets = payload["intent_buckets"]
        if not isinstance(intent_buckets, dict):
            raise ValueError(f"intent_buckets must be a mapping: {config_path}")
        for bucket_name, bucket in intent_buckets.items():
            if not isinstance(bucket_name, str) or not isinstance(bucket, dict):
                raise ValueError(f"intent_buckets must map strings to mappings: {config_path}")
            if "queries" not in bucket or not isinstance(bucket["queries"], list):
                raise ValueError(f"intent bucket {bucket_name} must define a query list: {config_path}")
            if "tool_plan" not in bucket or not isinstance(bucket["tool_plan"], list):
                raise ValueError(f"intent bucket {bucket_name} must define a tool_plan list: {config_path}")
            if "required_slots" in bucket and (
                not isinstance(bucket["required_slots"], list)
                or not all(isinstance(slot, str) for slot in bucket["required_slots"])
            ):
                raise ValueError(f"intent bucket {bucket_name} required_slots must be a string list: {config_path}")
    if "scene_tool_plan_map" in payload and not isinstance(payload["scene_tool_plan_map"], dict):
        raise ValueError(f"scene_tool_plan_map must be a mapping: {config_path}")
    if "scene_intent_map" in payload and not isinstance(payload["scene_intent_map"], dict):
        raise ValueError(f"scene_intent_map must be a mapping: {config_path}")
    return payload


def load_all_workflow_configs() -> dict[int, dict[str, Any]]:
    configs: dict[int, dict[str, Any]] = {}
    for path in sorted(workflow_dir().glob("*.yaml")):
        config = load_workflow_config(path)
        workflow_id = config["workflow_id"]
        if workflow_id in configs:
            raise ValueError(f"Duplicate workflow_id={workflow_id} in {path}")
        configs[workflow_id] = config
    return configs
