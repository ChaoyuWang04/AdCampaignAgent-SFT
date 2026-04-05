#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate rule-based RLVR benchmark cases."""

from __future__ import annotations

from typing import Any

if __package__ in {None, ""}:
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.benchmark.benchmark_schema import BenchmarkCase


def validate_case(case: BenchmarkCase) -> list[str]:
    errors: list[str] = []

    if case.expected_behavior in {"clarify", "reject"} and case.expected_tools:
        errors.append("clarify/reject case must not define expected_tools")
    if case.expected_behavior == "clarify" and not case.required_missing_slots:
        errors.append("clarify case must define required_missing_slots")
    if case.expected_behavior == "reject" and case.expected_tool_args:
        errors.append("reject case must not define expected_tool_args")
    if case.case_type == "sequential" and not case.expected_sequence:
        errors.append("sequential case must define expected_sequence")
    if case.case_type == "parallel" and not case.expected_parallel_groups:
        errors.append("parallel case must define expected_parallel_groups")
    if case.case_type == "parallel":
        repeated_tools = {
            tool_name
            for tool_name in case.expected_tools
            if case.expected_tools.count(tool_name) > 1
        }
        for tool_name in repeated_tools:
            args = case.expected_tool_args.get(tool_name)
            if not isinstance(args, list):
                errors.append(f"parallel repeated tool {tool_name} must use list expected_tool_args")
    return errors


def validate_cases(cases: list[BenchmarkCase]) -> list[str]:
    all_errors: list[str] = []
    for case in cases:
        for error in validate_case(case):
            all_errors.append(f"{case.id}: {error}")
    return all_errors

