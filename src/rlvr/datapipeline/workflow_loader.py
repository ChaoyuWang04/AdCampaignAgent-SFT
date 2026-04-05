from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


WORKFLOW_DIR = Path(__file__).resolve().parent / "workflow"
REQUIRED_FIELDS = {"workflow_id", "workflow_name", "count", "case_type"}


def workflow_dir() -> Path:
    return WORKFLOW_DIR


def load_workflow_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Workflow config must be a mapping: {config_path}")

    missing = REQUIRED_FIELDS - set(payload)
    if missing:
        raise ValueError(f"Workflow config missing required fields {sorted(missing)}: {config_path}")
    if "intent_buckets" not in payload or not isinstance(payload["intent_buckets"], dict):
        raise ValueError(f"Workflow config must define intent_buckets mapping: {config_path}")

    for bucket_name, bucket in payload["intent_buckets"].items():
        if not isinstance(bucket_name, str) or not isinstance(bucket, dict):
            raise ValueError(f"Intent buckets must map strings to mappings: {config_path}")
        if "queries" not in bucket or not isinstance(bucket["queries"], list):
            raise ValueError(f"Intent bucket {bucket_name} must define queries: {config_path}")
        if "rlvr_tags" in bucket and (
            not isinstance(bucket["rlvr_tags"], list)
            or not all(isinstance(item, str) for item in bucket["rlvr_tags"])
        ):
            raise ValueError(f"Intent bucket {bucket_name} rlvr_tags must be a string list: {config_path}")
    return payload


def load_all_workflow_configs() -> dict[int, dict[str, Any]]:
    configs: dict[int, dict[str, Any]] = {}
    for path in sorted(workflow_dir().glob("*.yaml")):
        config = load_workflow_config(path)
        workflow_id = int(config["workflow_id"])
        if workflow_id in configs:
            raise ValueError(f"Duplicate workflow_id={workflow_id} in {path}")
        configs[workflow_id] = config
    return configs

