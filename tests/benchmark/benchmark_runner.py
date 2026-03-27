#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""benchmark 执行主模块：统一封装本地/API runner 与整套评测聚合逻辑。

这个模块是 benchmark 的核心工程实现，负责三类事情：

1. 定义统一 runner 接口
   - 不同模型后端都实现 `run_case(case) -> trace`

2. 提供两种实际执行后端
   - `LocalHFCaseRunner`：本地 HuggingFace / transformers 模型
   - `OpenAICaseRunner`：OpenAI-compatible chat completions API

3. 提供整套 benchmark 聚合器
   - `BenchmarkSuiteRunner` 会逐条执行 case
   - 调用各层 evaluator 打分
   - 输出聚合结果和逐样本结果

依赖：
- 第三方库：`openai`、`transformers`、`torch`
- 项目内工具实现：`src.tools`
- 项目内路径配置：`src.common.project_paths`
- 项目内推理辅助函数：`src.inference.local_toolcall_repl`
- benchmark 子模块：schema、utils、各层 evaluator

是否可单独运行：
- 这个文件本身不是 CLI 入口
- 它不能直接通过命令行完成整个 benchmark
- 它是 [run_benchmark.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/tests/benchmark/run_benchmark.py) 的核心依赖模块

输入：
- 单条 `BenchmarkCase`，或一个 case 列表
- 模型后端配置，例如本地模型路径或 API 模型名

输出：
- 单条 case 执行后的标准化 trace
- 聚合后的 benchmark `report`
- 逐样本 `case_results.jsonl`

trace 说明：
- 输出 trace 统一为 `assistant / tool / assistant ...` 的消息列表
- 这样不同后端可以使用同一套 evaluator
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any, Protocol

from openai import OpenAI
from transformers import AutoModelForCausalLM, AutoTokenizer

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import torch
import src.tools as ad_tools
from src.common.project_paths import default_model_dir, tools_schema_path
from src.inference.local_toolcall_repl import (
    DEFAULT_CONTEXT,
    extract_assistant,
    extract_tool_calls,
    load_system_prompt,
    supports_tools_kw,
)
from tests.benchmark.benchmark_schema import BenchmarkCase
from tests.benchmark.benchmark_utils import ensure_results_dir, safe_mean
from tests.benchmark.eval_content import evaluate_content_case
from tests.benchmark.eval_format import evaluate_format_case
from tests.benchmark.eval_routing import evaluate_routing_case
from tests.benchmark.eval_system import evaluate_system_case


class CaseRunner(Protocol):
    """所有 benchmark 执行后端都要实现的最小接口。"""

    def run_case(self, case: BenchmarkCase) -> list[dict[str, Any]]:
        """执行单条 benchmark case，并返回标准化 trace。"""
        ...


class LocalHFCaseRunner:
    """用本地 HuggingFace 兼容模型执行 benchmark case。

    这个 runner 适合：
    - base model
    - 本地 LoRA / SFT 合并模型
    - 任意可被 `AutoModelForCausalLM` 和 `AutoTokenizer` 加载的本地模型

    不能单独作为命令行脚本运行，通常由 `run_benchmark.py` 调用。
    """

    def __init__(
        self,
        model_path: str | Path = default_model_dir(),
        max_new_tokens: int = 500,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int = 50,
        repetition_penalty: float = 1.0,
        no_repeat_ngram_size: int = 0,
        local_files_only: bool = True,
        bf16: bool = False,
        fp16: bool = False,
        device_map_auto: bool = False,
        max_tool_rounds: int = 4,
        system_text: str = "",
    ) -> None:
        """加载本地模型、tokenizer、工具 schema 与运行参数。

        输入：
        - 本地模型路径
        - 生成参数
        - 是否仅使用本地文件
        - 最大工具轮数

        输出：
        - 初始化后的 runner 实例
        """
        self.model_path = str(model_path)
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.repetition_penalty = repetition_penalty
        self.no_repeat_ngram_size = no_repeat_ngram_size
        self.local_files_only = local_files_only
        self.bf16 = bf16
        self.fp16 = fp16
        self.device_map_auto = device_map_auto
        self.max_tool_rounds = max_tool_rounds
        self.tools = json.loads(tools_schema_path().read_text(encoding="utf-8"))
        self.dispatch = {name: getattr(ad_tools, name) for name in ad_tools.__all__}

        model_dtype = None
        if self.bf16:
            model_dtype = torch.bfloat16
        elif self.fp16:
            model_dtype = torch.float16

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            local_files_only=local_files_only,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            local_files_only=local_files_only,
            dtype=model_dtype,
            device_map="auto" if self.device_map_auto else None,
        )
        if hasattr(self.model, "config"):
            self.model.config.use_cache = True
        self.system_prompt = system_text or load_system_prompt(
            argparse.Namespace(system_text="", system_file="")
        )

    def run_case(self, case: BenchmarkCase) -> list[dict[str, Any]]:
        """通过本地模型多轮生成与工具执行跑完一条 case。

        输入：
        - 一条 `BenchmarkCase`

        输出：
        - 标准化 trace，不包含初始的 system/user，仅保留后续 assistant/tool 轨迹
        """
        history: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_content(case)},
            {"role": "user", "content": case.user_input},
        ]

        tool_round = 0
        # 持续推进多轮 trace，直到模型停止调工具或达到安全轮数上限。
        while tool_round < self.max_tool_rounds:
            assistant_text = self._generate_once(history)
            normalized_calls = self._normalize_tool_calls(assistant_text)
            history.append(
                {
                    "role": "assistant",
                    "content": assistant_text,
                    **({"tool_calls": normalized_calls} if normalized_calls else {}),
                }
            )
            if not normalized_calls:
                break
            tool_round += 1
            for call in normalized_calls:
                history.append(self._execute_tool(call))

        return history[2:]

    def _build_system_content(self, case: BenchmarkCase) -> str:
        """把 case 上下文拼接进统一 system prompt。"""
        lines = [DEFAULT_CONTEXT.strip()]
        if case.context:
            lines.append("## Benchmark Case Context")
            for key, value in case.context.items():
                lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append(self.system_prompt)
        return "\n".join(lines).strip()

    def _render_messages(self, messages: list[dict[str, Any]]) -> torch.Tensor:
        """通过 chat template 将消息渲染成模型输入张量。"""
        template_kwargs: dict[str, Any] = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_tensors": "pt",
        }
        if supports_tools_kw(self.tokenizer):
            template_kwargs["tools"] = self.tools
        input_ids = self.tokenizer.apply_chat_template(messages, **template_kwargs)
        if isinstance(input_ids, torch.Tensor):
            tensor_input_ids = input_ids
        elif hasattr(input_ids, "input_ids"):
            raw_input_ids = input_ids.input_ids
            tensor_input_ids = (
                raw_input_ids
                if isinstance(raw_input_ids, torch.Tensor)
                else torch.tensor(raw_input_ids)
            )
        elif hasattr(input_ids, "ids"):
            raw_input_ids = input_ids.ids
            tensor_input_ids = (
                raw_input_ids
                if isinstance(raw_input_ids, torch.Tensor)
                else torch.tensor(raw_input_ids)
            )
        else:
            tensor_input_ids = torch.tensor(input_ids)
        if tensor_input_ids.ndim == 1:
            tensor_input_ids = tensor_input_ids.unsqueeze(0)
        return tensor_input_ids.to(self.model.device)

    def _generate_once(self, messages: list[dict[str, Any]]) -> str:
        """让本地模型生成单轮 assistant 输出。"""
        input_ids = self._render_messages(messages)
        attention_mask = torch.ones_like(input_ids)
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": self.max_new_tokens,
            "do_sample": self.temperature > 0,
            "repetition_penalty": self.repetition_penalty,
            "no_repeat_ngram_size": self.no_repeat_ngram_size,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        if generation_kwargs["do_sample"]:
            generation_kwargs["temperature"] = self.temperature
            generation_kwargs["top_p"] = self.top_p
            generation_kwargs["top_k"] = self.top_k
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                **generation_kwargs,
            )
        decoded = self.tokenizer.decode(output_ids[0], skip_special_tokens=False)
        return extract_assistant(decoded)

    def _normalize_tool_calls(self, assistant_text: str) -> list[dict[str, Any]]:
        """把原始提取到的 tool call 规范化为统一 trace 结构。"""
        normalized: list[dict[str, Any]] = []
        for index, call in enumerate(extract_tool_calls(assistant_text), start=1):
            name = call.get("name")
            arguments = call.get("arguments", {})
            if not isinstance(name, str) or not isinstance(arguments, dict):
                continue
            normalized.append(
                {
                    "id": f"call_{index}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
        return normalized

    def _execute_tool(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """执行本地工具实现，并生成对应的 tool message。"""
        name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])
        tool_fn = self.dispatch[name]
        filtered_arguments = self._filter_tool_arguments(tool_fn, arguments)
        try:
            result = tool_fn(**filtered_arguments)
        except TypeError as exc:
            result = {
                "status": "error",
                "error_type": "tool_argument_error",
                "tool_name": name,
                "message": str(exc),
                "original_arguments": arguments,
                "filtered_arguments": filtered_arguments,
            }
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(result, ensure_ascii=False),
        }

    def _filter_tool_arguments(
        self, tool_fn: Any, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """按真实函数签名过滤模型生成的多余参数，避免 benchmark 直接崩溃。"""
        try:
            signature = inspect.signature(tool_fn)
        except (TypeError, ValueError):
            return arguments
        accepted_names = {
            name
            for name, parameter in signature.parameters.items()
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        return {key: value for key, value in arguments.items() if key in accepted_names}


class OpenAICaseRunner:
    """用 OpenAI-compatible chat completions API 执行 benchmark case。

    这个 runner 适合：
    - OpenAI 官方接口
    - 兼容 OpenAI chat completions 协议的第三方模型服务

    依赖环境变量：
    - `OPENAI_API_KEY`
    - 可选：`OPENAI_BASE_URL`

    不能单独作为命令行脚本运行，通常由 `run_benchmark.py` 调用。
    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tool_rounds: int = 4,
        system_text: str = "",
    ) -> None:
        """初始化 API client、工具 schema 与运行参数。

        输入：
        - API 模型名
        - API key / base URL
        - 最大工具轮数

        输出：
        - 初始化后的 runner 实例
        """
        self.model_name = model_name
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
            base_url=base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        self.tools = json.loads(tools_schema_path().read_text(encoding="utf-8"))
        self.dispatch = {name: getattr(ad_tools, name) for name in ad_tools.__all__}
        self.max_tool_rounds = max_tool_rounds
        self.system_prompt = system_text or load_system_prompt(
            argparse.Namespace(system_text="", system_file="")
        )

    def run_case(self, case: BenchmarkCase) -> list[dict[str, Any]]:
        """通过 API 多轮生成与本地工具执行跑完一条 case。

        输入：
        - 一条 `BenchmarkCase`

        输出：
        - 标准化 trace，不包含初始的 system/user，仅保留后续 assistant/tool 轨迹
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_content(case)},
            {"role": "user", "content": case.user_input},
        ]
        tool_round = 0
        # 与本地 runner 保持一致，确保不同后端产出的 trace 可比较。
        while tool_round < self.max_tool_rounds:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
            )
            message = response.choices[0].message
            assistant_message = {
                "role": "assistant",
                "content": message.content or "",
            }
            if message.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in message.tool_calls
                ]
            messages.append(assistant_message)
            if not message.tool_calls:
                break
            tool_round += 1
            for tool_call in message.tool_calls:
                arguments = json.loads(tool_call.function.arguments)
                result = self.dispatch[tool_call.function.name](**arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
        return messages[2:]

    def _build_system_content(self, case: BenchmarkCase) -> str:
        """把 case 上下文拼接进统一 system prompt。"""
        lines = [DEFAULT_CONTEXT.strip()]
        if case.context:
            lines.append("## Benchmark Case Context")
            for key, value in case.context.items():
                lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append(self.system_prompt)
        return "\n".join(lines).strip()


class BenchmarkSuiteRunner:
    """批量运行 benchmark case，并输出聚合报告与逐样本结果。

    这是主 runner 的上层封装，负责把“单条 case 的执行”提升为“整套 benchmark 的执行”。

    它会：
    - 遍历全部 case
    - 为每条 case 调用后端 runner
    - 调用 format/routing/content/system 四层 evaluator
    - 聚合得到模型总分
    - 写出 report 与逐样本结果

    它不是独立 CLI，但会被 `run_benchmark.py` 直接调用。
    """

    def __init__(self, runner: CaseRunner, results_dir: str | Path) -> None:
        """绑定执行后端与 benchmark 结果输出目录。

        输入：
        - 已初始化好的后端 runner
        - 结果目录路径
        """
        self.runner = runner
        self.results_dir = ensure_results_dir(results_dir)

    def run(self, cases: list[BenchmarkCase], model_name: str) -> dict[str, Any]:
        """执行全部 case、完成打分，并返回聚合 benchmark 报告。

        输入：
        - `BenchmarkCase` 列表
        - 当前评测模型名

        输出：
        - 聚合报告 dict，结构与 `report.json` 一致
        """
        case_results: list[dict[str, Any]] = []
        for case in cases:
            trace = self.runner.run_case(case)
            format_scores = evaluate_format_case(case, trace)
            routing_scores = evaluate_routing_case(case, trace)
            content_scores = evaluate_content_case(case, trace)
            system_scores = evaluate_system_case(case, trace)
            scores = {
                **format_scores,
                **routing_scores,
                **content_scores,
                **system_scores,
            }
            case_results.append(
                {
                    "id": case.id,
                    "case_type": case.case_type,
                    "expected_behavior": case.expected_behavior,
                    "scores": scores,
                    "trace": trace,
                }
            )

        # 对所有样本的每个指标求平均，得到论文表格可直接使用的汇总结果。
        metric_names = sorted({name for item in case_results for name in item["scores"]})
        report = {
            "model": model_name,
            "case_count": len(cases),
            "metrics": {
                metric_name: safe_mean(
                    [float(item["scores"].get(metric_name, 0.0)) for item in case_results]
                )
                for metric_name in metric_names
            },
        }
        self._write_outputs(report, case_results)
        return report

    def _write_outputs(self, report: dict[str, Any], case_results: list[dict[str, Any]]) -> None:
        """把聚合报告与逐样本结果写入磁盘。

        输出文件：
        - `report.json`
        - `case_results.jsonl`
        """
        (self.results_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with (self.results_dir / "case_results.jsonl").open("w", encoding="utf-8") as handle:
            for item in case_results:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
