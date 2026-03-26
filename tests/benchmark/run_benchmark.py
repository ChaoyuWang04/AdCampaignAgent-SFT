#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""benchmark 命令行入口。

这个脚本是 `tests/benchmark/` 目录下真正的主入口，负责把整套 benchmark 串起来执行。

它会完成以下流程：
- 解析命令行参数
- 从 `data/` 目录加载一个或多个 benchmark case 文件
- 根据参数选择本地模型后端或 OpenAI-compatible API 后端
- 调用 `BenchmarkSuiteRunner` 运行整套评测
- 在终端打印聚合指标
- 在结果目录写出 `report.json` 与 `case_results.jsonl`

依赖：
- 项目内路径工具：`src.common.project_paths`
- benchmark 主逻辑：`tests.benchmark.benchmark_runner`
- benchmark schema：`tests.benchmark.benchmark_schema`

是否可单独运行：
- 可以，且它就是推荐的 benchmark 运行入口
- 支持本地 `transformers` 模型与 OpenAI-compatible API 两种后端

输入：
- 命令行参数
  - `--backend`：`local_hf` 或 `openai`
  - `--model`：本地模型路径或 API 模型名
  - `--data-dir`：样本目录
  - `--results-dir`：结果目录
  - `--case-files`：指定要跑的样本文件

输出：
- 终端中的聚合指标摘要
- 磁盘中的 benchmark 结果文件

输出文件说明：
- `report.json`：论文表格或实验对比所需的聚合分数
- `case_results.jsonl`：逐样本 trace 与各项得分，方便排查失败案例
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common.project_paths import tests_dir
from tests.benchmark.benchmark_runner import (
    BenchmarkSuiteRunner,
    LocalHFCaseRunner,
    OpenAICaseRunner,
)
from tests.benchmark.benchmark_schema import load_cases

DEFAULT_CASE_FILES = [
    "test_standard.json",
    "test_sequential.json",
    "test_parallel.json",
    "test_oos.json",
    "test_clarify.json",
]

CASE_FILE_GROUPS = {
    "all": DEFAULT_CASE_FILES,
    "format": [
        "test_standard.json",
        "test_sequential.json",
        "test_parallel.json",
    ],
    "routing": [
        "test_standard.json",
        "test_sequential.json",
        "test_parallel.json",
        "test_oos.json",
        "test_clarify.json",
    ],
    "content": [
        "test_standard.json",
    ],
    "system": [
        "test_sequential.json",
        "test_parallel.json",
        "test_oos.json",
        "test_clarify.json",
    ],
}

METRIC_GROUPS = {
    "all": ["F1", "F2", "R1", "R2", "R3", "C1", "C2", "S1", "S2", "S3", "S4", "S5"],
    "format": ["F1", "F2"],
    "routing": ["R1", "R2", "R3"],
    "content": ["C1", "C2"],
    "system": ["S1", "S2", "S3", "S4", "S5"],
}


def parse_args() -> argparse.Namespace:
    """解析命令行参数，包括后端、模型、数据目录与结果目录。"""
    parser = argparse.ArgumentParser(description="Run AdCampaignAgent benchmark suite")
    parser.add_argument(
        "--backend",
        choices=["local_hf", "openai"],
        required=True,
        help="Model execution backend",
    )
    parser.add_argument("--model", required=True, help="Local model path or API model name")
    parser.add_argument("--max-new-tokens", type=int, default=500, help="Max new tokens for local HF generation")
    parser.add_argument("--temperature", type=float, default=0.0, help="Sampling temperature for local HF generation")
    parser.add_argument("--top-p", type=float, default=1.0, help="Top-p sampling value for local HF generation")
    parser.add_argument("--top-k", type=int, default=50, help="Top-k sampling value for local HF generation")
    parser.add_argument(
        "--repetition-penalty",
        type=float,
        default=1.0,
        help="Repetition penalty for local HF generation",
    )
    parser.add_argument(
        "--no-repeat-ngram-size",
        type=int,
        default=0,
        help="Block repeated ngrams of this size for local HF generation",
    )
    parser.add_argument("--max-tool-rounds", type=int, default=4, help="Max tool-execution rounds per case")
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Load local HF model/tokenizer using only local files",
    )
    parser.add_argument(
        "--eval-group",
        choices=["all", "format", "routing", "content", "system"],
        default="all",
        help="Run all metrics or only a metric group",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=tests_dir() / "benchmark" / "data",
        help="Directory containing benchmark case JSON files",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=tests_dir() / "benchmark" / "results",
        help="Directory to write benchmark outputs",
    )
    parser.add_argument(
        "--case-files",
        nargs="*",
        default=None,
        help="Subset of case files to run",
    )
    return parser.parse_args()


def resolve_case_files(eval_group: str, case_files: list[str] | None = None) -> list[str]:
    """根据评测分组与用户显式指定的文件列表，确定本次要运行的 case 文件。"""
    if case_files:
        return case_files
    return CASE_FILE_GROUPS[eval_group]


def select_metrics(report: dict, eval_group: str) -> dict:
    """按评测分组过滤聚合报告中的指标，便于单独查看某一层结果。"""
    selected_metric_names = set(METRIC_GROUPS[eval_group])
    return {
        **report,
        "metrics": {
            metric_name: value
            for metric_name, value in report["metrics"].items()
            if metric_name in selected_metric_names
        },
    }


def build_runner(args: argparse.Namespace):
    """根据 CLI 参数构建 benchmark 执行后端。"""
    if args.backend == "local_hf":
        return LocalHFCaseRunner(
            model_path=args.model,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            repetition_penalty=args.repetition_penalty,
            no_repeat_ngram_size=args.no_repeat_ngram_size,
            local_files_only=args.local_files_only,
            max_tool_rounds=args.max_tool_rounds,
        )
    return OpenAICaseRunner(model_name=args.model, max_tool_rounds=args.max_tool_rounds)


def main() -> None:
    """加载样本、执行 benchmark，并打印聚合指标摘要。"""
    args = parse_args()
    case_files = resolve_case_files(args.eval_group, args.case_files)
    cases = []
    for file_name in case_files:
        cases.extend(load_cases(args.data_dir / file_name))

    # 保持后端选择显式可控，便于同一命令风格比较本地与 API 模型。
    runner = build_runner(args)

    suite_runner = BenchmarkSuiteRunner(runner=runner, results_dir=args.results_dir)
    report = suite_runner.run(cases=cases, model_name=args.model)
    report = select_metrics(report, args.eval_group)
    (args.results_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"model: {report['model']}")
    print(f"cases: {report['case_count']}")
    print(f"eval_group: {args.eval_group}")
    for metric_name, value in sorted(report["metrics"].items()):
        print(f"{metric_name}: {value:.4f}")


if __name__ == "__main__":
    main()
