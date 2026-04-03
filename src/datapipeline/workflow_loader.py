from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


WORKFLOW_DIR = Path(__file__).resolve().parent / "workflow"
REQUIRED_FIELDS = {"workflow_id", "workflow_name", "count", "tool_plans"}


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

    if not isinstance(payload["tool_plans"], list):
        raise ValueError(f"tool_plans must be a list: {config_path}")
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
