#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build RLVR benchmark cases from rule-based seeds."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.common.project_paths import data_dir
try:
    from benchmark_schema import BenchmarkCase
except ModuleNotFoundError:
    try:
        from src.benchmark.benchmark_schema import BenchmarkCase
    except ModuleNotFoundError:
        import sys

        sys.path.append(str(Path(__file__).resolve().parents[3] / "src" / "benchmark"))
        from benchmark_schema import BenchmarkCase


def flatten_tool_plan(tool_plan: list[dict[str, Any]]) -> list[str]:
    flattened: list[str] = []
    for group in tool_plan:
        flattened.extend(group.get("tools", []))
    return flattened


def parallel_groups(tool_plan: list[dict[str, Any]]) -> list[list[str]]:
    return [list(group.get("tools", [])) for group in tool_plan if group.get("mode") == "parallel" and group.get("tools")]


def build_case_from_seed(seed: dict[str, Any]) -> BenchmarkCase:
    tool_plan = list(seed.get("tool_plan", []))
    expected_behavior = seed.get("expected_behavior", "tool_call")
    expected_tools = flatten_tool_plan(tool_plan) if expected_behavior == "tool_call" else []
    case_type = seed.get("case_type", "standard")
    expected_sequence = expected_tools if case_type == "sequential" else []
    expected_parallel_groups = parallel_groups(tool_plan) if case_type == "parallel" else []
    benchmark_case_type = "oos" if expected_behavior == "reject" else case_type

    return BenchmarkCase(
        id=seed["id"],
        case_type=benchmark_case_type,
        user_input=seed["user_input"],
        context=dict(seed.get("context", {})),
        expected_behavior=expected_behavior,
        expected_tools=expected_tools,
        expected_tool_args=dict(seed.get("expected_tool_args", {})),
        expected_sequence=expected_sequence,
        expected_parallel_groups=expected_parallel_groups,
        required_missing_slots=list(seed.get("required_missing_slots", [])),
        rejection_category=seed.get("rejection_category"),
        notes=seed.get("notes", ""),
        rlvr_weight=float(seed.get("rlvr_weight", 1.0)),
        rlvr_split=str(seed.get("rlvr_split", "train")),
        rlvr_tags=list(seed.get("rlvr_tags", [])),
        rlvr_max_tool_rounds=seed.get("rlvr_max_tool_rounds"),
    )


def build_cases(seeds: list[dict[str, Any]]) -> list[BenchmarkCase]:
    return [build_case_from_seed(seed) for seed in seeds]


def _default_input_path() -> Path:
    raw_dir = data_dir() / "rlvr" / "raw"
    candidates = sorted(raw_dir.glob("rlvr_seeds_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No RLVR seed files found in {raw_dir}")
    return candidates[-1]


def _default_output_path() -> Path:
    return data_dir() / "rlvr" / "processed" / "rlvr_cases.json"


def main(input_path: str | Path | None = None, output_path: str | Path | None = None) -> list[BenchmarkCase]:
    source_path = Path(input_path) if input_path is not None else _default_input_path()
    seeds = json.loads(source_path.read_text(encoding="utf-8"))
    cases = build_cases(seeds)
    target_path = Path(output_path) if output_path is not None else _default_output_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(case) for case in cases]
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return cases


if __name__ == "__main__":
    main()
