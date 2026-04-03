#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-turn GRPO 训练桥接层。

这个文件负责把：
- benchmark case
- multi-turn rollout
- benchmark-based reward

接到 TRL 的 `GRPOTrainer` 上。

核心问题：
- TRL 默认更偏向“单次 completion”范式
- 但我们的 agent 是多轮 tool-calling trace

因此这里需要：
- 自定义 rollout 生成
- 把 multi-turn assistant token 展平成 flat completion
- 保留 trace cache 供 reward 回查
- 补齐 TRL / GRPO 所需的 old/ref logprob 字段
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
import copy
import inspect
import os
import sys

import torch

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

try:
    from trl import GRPOConfig, GRPOTrainer
except ModuleNotFoundError:
    venv_lib = Path(__file__).resolve().parents[2] / ".venv" / "lib"
    for candidate in sorted(venv_lib.glob("python*/site-packages")):
        sys.path.insert(0, str(candidate))
    from trl import GRPOConfig, GRPOTrainer

from src.rlvr.reward import compute_reward
from src.rlvr.rollout import RolloutTrace, run_rollout

try:
    from src.benchmark.benchmark_schema import BenchmarkCase
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))
    from benchmark_schema import BenchmarkCase


def build_trl_reward_func(case_lookup: dict[str, BenchmarkCase]) -> Callable[..., list[float]]:
    """构造 TRL 风格 reward function，通过 trace cache 回查完整 rollout。"""
    def _reward_func(
        prompts: list[Any],
        completions: list[str],
        trace_ids: list[str],
        trainer: "MultiTurnGRPOTrainer",
        **kwargs,
    ) -> list[float]:
        _ = prompts
        _ = completions
        _ = kwargs
        rewards: list[float] = []
        for trace_id in trace_ids:
            trace = trainer._trace_cache[trace_id]
            case_id = trainer._trace_case_ids[trace_id]
            case = case_lookup[case_id]
            rewards.append(compute_reward(trace, case).total)
        return rewards

    return _reward_func


class _FakeAccelerator:
    """供 smoke test 使用的最小 accelerator 替身。"""
    def __init__(self, device: torch.device | None = None) -> None:
        self.device = device or torch.device("cpu")
        self.num_processes = 1
        self.process_index = 0
        self.is_main_process = True

    def gather(self, value):
        return value

    def unwrap_model(self, model):
        return model


@dataclass(slots=True)
class MultiTurnGenerationResult:
    """保存一次 generation phase 产出的全部中间结果。"""
    prompt_ids: list[list[int]]
    completion_ids: list[list[int]]
    logprobs: list[list[float]]
    trace_ids: list[str]
    case_ids: list[str]
    completions_text: list[str]


class MultiTurnGRPOTrainer(GRPOTrainer):
    """将 multi-turn rollout 适配到 TRL GRPO 的自定义 trainer。"""
    def __init__(
        self,
        *args,
        case_lookup: dict[str, BenchmarkCase],
        rollout_runner: Callable[..., RolloutTrace] = run_rollout,
        max_tool_rounds: int = 4,
        tool_schemas: list[dict[str, Any]] | None = None,
        reward_func: Callable[..., list[float]] | None = None,
        **kwargs,
    ):
        self._trace_cache: dict[str, RolloutTrace] = {}
        self._trace_case_ids: dict[str, str] = {}
        self._generate_completions_call_count = 0
        self._reward_call_count = 0
        self._trace_seq = 0
        self.case_lookup = case_lookup
        self.rollout_runner = rollout_runner
        self.max_tool_rounds = max_tool_rounds
        self.tool_schemas = tool_schemas or []
        self.multi_turn_reward_func = reward_func or build_trl_reward_func(case_lookup)
        super().__init__(*args, **kwargs)

    @classmethod
    def for_testing(
        cls,
        *,
        model,
        tokenizer,
        reward_func: Callable[..., list[float]],
        case_lookup: dict[str, BenchmarkCase],
        rollout_runner: Callable[..., RolloutTrace],
        num_generations: int = 2,
        max_tool_rounds: int = 4,
    ) -> "MultiTurnGRPOTrainer":
        """构造一个不依赖完整 Trainer 初始化链路的测试版 trainer。"""
        trainer = object.__new__(cls)
        trainer.model = model
        trainer.processing_class = tokenizer
        trainer.reward_funcs = [reward_func]
        trainer.reward_func_names = ["benchmark_reward"]
        trainer.reward_weights = torch.ones(1, dtype=torch.float32)
        trainer.reward_processing_classes = [None]
        trainer.case_lookup = case_lookup
        trainer.rollout_runner = rollout_runner
        trainer.max_tool_rounds = max_tool_rounds
        trainer.tool_schemas = []
        trainer.multi_turn_reward_func = reward_func
        trainer._trace_cache = {}
        trainer._trace_case_ids = {}
        trainer._generate_completions_call_count = 0
        trainer._reward_call_count = 0
        trainer._trace_seq = 0
        trainer.accelerator = _FakeAccelerator()
        trainer.args = SimpleNamespace(
            per_device_train_batch_size=1,
            per_device_eval_batch_size=1,
            gradient_accumulation_steps=1,
            steps_per_generation=1,
            gradient_checkpointing_kwargs={},
            report_to=[],
            delta=None,
            sapo_temperature_pos=1.0,
            sapo_temperature_neg=1.05,
            use_bias_correction_kl=False,
        )
        trainer.beta = 0.0
        trainer.temperature = 1.0
        trainer.use_liger_kernel = False
        trainer.top_entropy_quantile = 1.0
        trainer.off_policy_mask_threshold = None
        trainer.importance_sampling_level = "token"
        trainer.loss_type = "grpo"
        trainer.num_iterations = 1
        trainer.epsilon_low = 0.2
        trainer.epsilon_high = 0.2
        trainer.use_vllm = False
        trainer.vllm_importance_sampling_correction = False
        trainer.mask_truncated_completions = False
        trainer.chat_template_kwargs = {}
        trainer.tools = []
        trainer.environments = None
        trainer.current_gradient_accumulation_steps = 1
        trainer.max_completion_length = 256
        trainer.pad_token_id = getattr(tokenizer, "pad_token_id", 0)
        trainer.eos_token_id = getattr(tokenizer, "eos_token_id", 1)
        trainer.ref_model = None
        trainer._metrics = {"train": defaultdict(list), "eval": defaultdict(list)}
        trainer._logs = {"prompt": [], "completion": [], "rewards": defaultdict(list), "advantages": []}
        trainer.state = SimpleNamespace(global_step=0, num_input_tokens_seen=0)
        trainer.model_kwarg_keys = inspect.signature(model.forward).parameters.keys()
        trainer.num_generations = num_generations
        trainer.num_generations_eval = num_generations
        return trainer

    def _encode_prompt_messages(self, messages: list[dict[str, Any]]) -> list[int]:
        """把 message list 编码成 prompt token ids。"""
        tokenized = self.processing_class.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors=None,
            tools=self.tool_schemas if self.tool_schemas else None,
        )
        if isinstance(tokenized, torch.Tensor):
            return tokenized.squeeze(0).tolist()
        if hasattr(tokenized, "input_ids"):
            return list(tokenized.input_ids)
        return list(tokenized)

    def _flatten_trace(self, trace: RolloutTrace) -> tuple[list[int], list[float], str]:
        """
        把 multi-turn trace 展平成单段 completion。

        输出：
        - token_ids: 所有 assistant turn token 顺序拼接后的结果
        - logprobs: 与 token_ids 一一对齐
        - text: 所有 assistant 文本拼接后的可读版本

        为什么要 flatten multi-turn trace：
        - TRL 的 GRPO loss 仍然要求一个“completion token 序列”
        - 我们不能把 tool message 直接塞进 policy loss，因为它们是环境反馈，不是 policy 输出
        - 因此最自然的做法是：只保留 assistant role 生成的 token，并按时间顺序拼成一段 flat completion
        - 这样 advantage 就能覆盖整条 multi-turn assistant 行为，而不破坏 TRL 现有的 loss 入口
        """
        token_ids: list[int] = []
        logprobs: list[float] = []
        assistant_texts: list[str] = []
        for turn in trace.assistant_turns:
            token_ids.extend(turn.token_ids)
            logprobs.extend(turn.logprobs)
            assistant_texts.append(turn.assistant_text)
        return token_ids, logprobs, "\n".join(assistant_texts).strip()

    def _generate_completions(
        self,
        prompts: list[list[dict[str, Any]]],
        case_ids: list[str],
    ) -> MultiTurnGenerationResult:
        """
        对一批 prompt 执行真实 multi-turn rollout。

        这里不会走 TRL 默认的单轮 completion 生成，而是：
        - 每个 prompt 跑完整 `run_rollout`
        - 生成 `RolloutTrace`
        - 再把 trace 转成 GRPO 可消费的 flat completion
        """
        self._generate_completions_call_count += 1

        prompt_ids_list: list[list[int]] = []
        completion_ids_list: list[list[int]] = []
        logprobs_list: list[list[float]] = []
        trace_ids: list[str] = []
        expanded_case_ids: list[str] = []
        completions_text: list[str] = []

        num_generations = self.num_generations if getattr(self.model, "training", True) else self.num_generations_eval
        for prompt_messages, case_id in zip(prompts, case_ids, strict=True):
            encoded_prompt = self._encode_prompt_messages(prompt_messages)
            case = self.case_lookup[case_id]
            for _ in range(num_generations):
                # 每个 generation 对应一条独立 rollout。
                trace = self.rollout_runner(
                    model=self.model,
                    tokenizer=self.processing_class,
                    messages=copy.deepcopy(prompt_messages),
                    tools=self.tool_schemas,
                    max_tool_rounds=self.max_tool_rounds,
                    case=case,
                )
                completion_ids, logprobs, completion_text = self._flatten_trace(trace)
                if not completion_ids:
                    # 没有 assistant token 时补一个 eos，避免后续张量形状为空。
                    completion_ids = [self.eos_token_id]
                    logprobs = [0.0]
                trace_id = f"{case_id}::trace::{self._trace_seq}"
                self._trace_seq += 1
                self._trace_cache[trace_id] = trace
                self._trace_case_ids[trace_id] = case_id

                prompt_ids_list.append(encoded_prompt)
                completion_ids_list.append(completion_ids)
                logprobs_list.append(logprobs)
                trace_ids.append(trace_id)
                expanded_case_ids.append(case_id)
                completions_text.append(completion_text)

        return MultiTurnGenerationResult(
            prompt_ids=prompt_ids_list,
            completion_ids=completion_ids_list,
            logprobs=logprobs_list,
            trace_ids=trace_ids,
            case_ids=expanded_case_ids,
            completions_text=completions_text,
        )

    def _compute_group_advantages(self, rewards: torch.Tensor, num_generations: int) -> torch.Tensor:
        """按 GRPO 的 group 维度做标准化 advantage。"""
        grouped = rewards.view(-1, num_generations)
        grouped_mean = grouped.mean(dim=1, keepdim=True)
        grouped_std = grouped.std(dim=1, keepdim=True)
        return ((grouped - grouped_mean) / (grouped_std + 1e-4)).view(-1)

    def _compute_ref_logprobs(
        self,
        *,
        prompt_ids: torch.Tensor,
        prompt_mask: torch.Tensor,
        completion_ids: torch.Tensor,
        completion_mask: torch.Tensor,
    ) -> torch.Tensor:
        """
        计算 reference model 在同一段 flat completion 上的逐 token logprob。

        这一步用于 TRL 内部的 KL 项。
        如果当前没有独立 ref model，则返回全零张量，让训练链路先保持可运行。
        """
        if self.ref_model is None:
            return torch.zeros_like(completion_ids, dtype=torch.float32)

        prompt_completion_ids = torch.cat([prompt_ids, completion_ids], dim=1)
        attention_mask = torch.cat([prompt_mask, completion_mask], dim=1)
        logits_to_keep = completion_ids.size(1)
        batch_size = (
            self.args.per_device_train_batch_size
            if getattr(self.model, "training", True)
            else self.args.per_device_eval_batch_size
        )
        with torch.no_grad():
            ref_per_token_logps, _ = self._get_per_token_logps_and_entropies(
                self.ref_model,
                prompt_completion_ids,
                attention_mask,
                logits_to_keep,
                batch_size=batch_size,
            )
        return ref_per_token_logps

    def _generate_and_score_completions(
        self, inputs: list[dict[str, torch.Tensor | Any]]
    ) -> dict[str, torch.Tensor | Any]:
        """
        重写 TRL 的 generation + scoring 阶段。

        这里是 multi-turn GRPO 的真正接入点：
        - 输入是一批 prompt
        - 内部执行 rollout
        - 输出必须整理成 TRL 后续 `_compute_loss` 能接受的字段
        """
        device = self.accelerator.device
        prompts = [item["prompt"] for item in inputs]
        case_ids = [item["case_id"] for item in inputs]

        result = self._generate_completions(prompts, case_ids)

        # 先把变长 sequence 组装成张量，便于后续 padding 和 loss 计算。
        prompt_tensors = [torch.tensor(ids, device=device, dtype=torch.long) for ids in result.prompt_ids]
        prompt_masks = [torch.ones_like(ids, dtype=torch.long) for ids in prompt_tensors]
        completion_tensors = [torch.tensor(ids, device=device, dtype=torch.long) for ids in result.completion_ids]
        completion_masks = [torch.ones_like(ids, dtype=torch.long) for ids in completion_tensors]
        sampling_logprobs = [torch.tensor(logps, device=device, dtype=torch.float32) for logps in result.logprobs]

        from trl.trainer.utils import pad

        # TRL 后续所有 loss 逻辑都假设这里已经是按 batch 对齐的张量。
        prompt_ids = pad(prompt_tensors, padding_value=self.pad_token_id, padding_side="left")
        prompt_mask = pad(prompt_masks, padding_value=0, padding_side="left")
        completion_ids = pad(completion_tensors, padding_value=self.pad_token_id, padding_side="right")
        completion_mask = pad(completion_masks, padding_value=0, padding_side="right")
        old_per_token_logps = pad(sampling_logprobs, padding_value=0.0, padding_side="right")
        ref_per_token_logps = self._compute_ref_logprobs(
            prompt_ids=prompt_ids,
            prompt_mask=prompt_mask,
            completion_ids=completion_ids,
            completion_mask=completion_mask,
        )

        self._reward_call_count += 1
        # reward 不直接看 completion 文本，而是通过 trace cache 回到完整 rollout 上评分。
        rewards_list = self.multi_turn_reward_func(
            prompts=prompts,
            completions=result.completions_text,
            trace_ids=result.trace_ids,
            case_ids=result.case_ids,
            trainer=self,
        )
        rewards = torch.tensor(rewards_list, device=device, dtype=torch.float32)
        num_generations = self.num_generations if getattr(self.model, "training", True) else self.num_generations_eval
        advantages = self._compute_group_advantages(rewards, num_generations=num_generations)

        self._logs["advantages"].extend(advantages.tolist())

        return {
            "prompt_ids": prompt_ids,
            "prompt_mask": prompt_mask,
            "completion_ids": completion_ids,
            "completion_mask": completion_mask,
            "advantages": advantages,
            "old_per_token_logps": old_per_token_logps,
            "ref_per_token_logps": ref_per_token_logps,
            # 这里必须是按样本展开的一维 tensor，而不是标量；
            # TRL 会在 `_prepare_inputs` 里对整个 dict 做 shuffle / split。
            "num_items_in_batch": completion_mask.sum(dim=1).to(dtype=torch.long),
        }


def build_train_dataset(
    cases: list[BenchmarkCase],
    *,
    history: list[dict[str, Any]] | None = None,
):
    """把 case 列表变成 TRL / datasets 可直接消费的训练集。"""
    from datasets import Dataset

    from src.rlvr.prompt_builder import build_case_messages

    rows = []
    for case in cases:
        rows.append(
            {
                "prompt": build_case_messages(case, history=history),
                "case_id": case.id,
                "case_type": case.case_type,
            }
        )
    return Dataset.from_list(rows)


def default_reward_logger(trainer: MultiTurnGRPOTrainer, trace_ids: list[str], rewards: list[float]) -> None:
    """把 reward 写进 trainer 内部日志缓存，方便后续调试。"""
    for trace_id, reward in zip(trace_ids, rewards, strict=True):
        trainer._logs["rewards"]["benchmark_reward"].append(float(reward))
