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
        default=[
            "test_standard.json",
            "test_sequential.json",
            "test_parallel.json",
            "test_oos.json",
            "test_clarify.json",
        ],
        help="Subset of case files to run",
    )
    return parser.parse_args()


def main() -> None:
    """加载样本、执行 benchmark，并打印聚合指标摘要。"""
    args = parse_args()
    cases = []
    for file_name in args.case_files:
        cases.extend(load_cases(args.data_dir / file_name))

    # 保持后端选择显式可控，便于同一命令风格比较本地与 API 模型。
    if args.backend == "local_hf":
        runner = LocalHFCaseRunner(model_path=args.model)
    else:
        runner = OpenAICaseRunner(model_name=args.model)

    suite_runner = BenchmarkSuiteRunner(runner=runner, results_dir=args.results_dir)
    report = suite_runner.run(cases=cases, model_name=args.model)
    print(f"model: {report['model']}")
    print(f"cases: {report['case_count']}")
    for metric_name, value in sorted(report["metrics"].items()):
        print(f"{metric_name}: {value:.4f}")


if __name__ == "__main__":
    main()
