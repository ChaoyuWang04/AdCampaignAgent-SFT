#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试 benchmark CLI 的样本分组与指标过滤逻辑。"""

from argparse import Namespace

import tests.benchmark.run_benchmark as run_benchmark_module
from tests.benchmark.run_benchmark import (
    DEFAULT_CASE_FILES,
    METRIC_GROUPS,
    build_runner,
    resolve_case_files,
    select_metrics,
)


def test_resolve_case_files_for_all_uses_default_set() -> None:
    """运行整套 benchmark 时应使用默认的全部 case 文件。"""
    assert resolve_case_files("all") == DEFAULT_CASE_FILES


def test_resolve_case_files_for_system_group_uses_specialized_cases() -> None:
    """系统层单独运行时应只选系统相关的样本文件。"""
    assert resolve_case_files("system") == [
        "test_sequential.json",
        "test_parallel.json",
        "test_oos.json",
        "test_clarify.json",
    ]


def test_select_metrics_filters_report_by_group() -> None:
    """单独运行某个指标组时应只保留该组对应的聚合指标。"""
    report = {
        "model": "demo",
        "case_count": 3,
        "metrics": {
            "F1": 1.0,
            "F2": 1.0,
            "R1": 0.9,
            "C1": 0.8,
            "S5": 0.7,
        },
    }

    filtered = select_metrics(report, "format")

    assert filtered["metrics"] == {"F1": 1.0, "F2": 1.0}
    assert METRIC_GROUPS["format"] == ["F1", "F2"]


def test_build_runner_passes_local_generation_config(monkeypatch) -> None:
    """本地 runner 应接收从 CLI 暴露出来的生成参数。"""
    args = Namespace(
        backend="local_hf",
        model="/tmp/demo-model",
        max_new_tokens=321,
        temperature=0.2,
        top_p=0.85,
        top_k=17,
        repetition_penalty=1.08,
        no_repeat_ngram_size=5,
        max_tool_rounds=6,
        local_files_only=False,
        bf16=True,
        fp16=False,
        device_map_auto=True,
    )
    captured = {}

    class DummyRunner:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.__dict__.update(kwargs)

    monkeypatch.setattr(run_benchmark_module, "LocalHFCaseRunner", DummyRunner)

    runner = build_runner(args)

    assert runner.max_new_tokens == 321
    assert captured["temperature"] == 0.2
    assert captured["top_p"] == 0.85
    assert captured["top_k"] == 17
    assert captured["repetition_penalty"] == 1.08
    assert captured["no_repeat_ngram_size"] == 5
    assert captured["max_tool_rounds"] == 6
    assert captured["local_files_only"] is False
    assert captured["bf16"] is True
    assert captured["fp16"] is False
    assert captured["device_map_auto"] is True
