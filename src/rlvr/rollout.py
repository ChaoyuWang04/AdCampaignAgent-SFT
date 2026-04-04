#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多轮 tool-calling rollout 执行引擎。

职责：
- 给定当前 message history，让模型生成一轮 assistant 输出
- 解析其中的 tool call
- 执行工具
- 把 tool result 追加回 history
- 持续循环，直到不再调用工具或达到最大轮数

输出：
- `RolloutTrace`
  - 每一轮 assistant token ids / logprobs
  - tool call 解析结果
  - tool execution 结果
  - 完整 message history
  - 终止原因

和 GRPO / RLVR 的关系：
- rollout 是 RLVR 的“环境执行”阶段
- reward 看的是整条 trace
- trainer 后面只会取 assistant token 参与 GRPO loss；tool result 本身不作为 policy 直接优化对象
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any
import uuid

import torch

import src.tools as ad_tools
from src.inference.local_toolcall_repl import (
    extract_assistant,
    extract_tool_calls,
    supports_tools_kw,
)
try:
    from src.benchmark.benchmark_schema import BenchmarkCase
except ModuleNotFoundError:
    BenchmarkCase = Any


DEFAULT_MAX_NEW_TOKENS = 512
_TOOL_DISPATCH: dict[str, Any] = {
    name: getattr(ad_tools, name) for name in ad_tools.__all__
}


@dataclass(slots=True)
class AssistantTurnTrace:
    """记录单个 assistant turn 的训练关键信息。"""
    assistant_text: str
    token_ids: list[int]
    logprobs: list[float]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_messages: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class RolloutTrace:
    """记录一条完整 multi-turn rollout 的全部信息。"""
    assistant_turns: list[AssistantTurnTrace]
    tool_messages: list[dict[str, Any]]
    message_history: list[dict[str, Any]]
    termination_reason: str


def _render_messages(
    tokenizer,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> torch.Tensor:
    """把当前对话 history 渲染成模型输入 token。"""
    template_kwargs: dict[str, Any] = {
        "tokenize": True,
        "add_generation_prompt": True,
        "return_tensors": "pt",
    }
    if tools and supports_tools_kw(tokenizer):
        template_kwargs["tools"] = tools

    input_ids = tokenizer.apply_chat_template(messages, **template_kwargs)
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
    return tensor_input_ids


def _compute_token_logprobs(
    scores: list[torch.Tensor],
    generated_ids: torch.Tensor,
) -> list[float]:
    """把 generate 返回的 step scores 还原为逐 token logprob。"""
    logprobs: list[float] = []
    for step_scores, token_id in zip(scores, generated_ids.tolist()):
        log_probs = torch.log_softmax(step_scores[0], dim=-1)
        logprobs.append(float(log_probs[token_id].item()))
    return logprobs


def _generate_assistant_turn(
    model,
    tokenizer,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> tuple[str, list[int], list[float]]:
    """
    生成单轮 assistant 回复，并返回 token ids 与 logprobs。

    `token_ids / logprobs` 是后续 GRPO loss 的直接来源。
    """
    if hasattr(model, "rlvr_generate"):
        result = model.rlvr_generate(messages=messages, tokenizer=tokenizer)
        return (
            result["assistant_text"],
            list(result["token_ids"]),
            list(result["logprobs"]),
        )

    input_ids = _render_messages(tokenizer, messages, tools)
    device = getattr(model, "device", None)
    if device is not None:
        input_ids = input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)

    with torch.no_grad():
        output = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=DEFAULT_MAX_NEW_TOKENS,
            return_dict_in_generate=True,
            output_scores=True,
        )

    full_sequence = output.sequences[0]
    prompt_length = input_ids.shape[-1]
    generated_ids = full_sequence[prompt_length:]
    decoded = tokenizer.decode(full_sequence, skip_special_tokens=False)
    assistant_text = extract_assistant(decoded)
    logprobs = _compute_token_logprobs(output.scores, generated_ids)
    return assistant_text, generated_ids.tolist(), logprobs


def _normalize_tool_calls(assistant_text: str) -> tuple[list[dict[str, Any]], bool]:
    """把 assistant 文本中的 tool call 片段转成统一结构，并标记是否出现坏格式调用。"""
    parsed_calls = extract_tool_calls(assistant_text)
    normalized: list[dict[str, Any]] = []
    saw_malformed_call = False
    for call in parsed_calls:
        name = call.get("name")
        arguments = call.get("arguments", {})
        if not name or not isinstance(arguments, dict):
            saw_malformed_call = True
            continue
        normalized.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
        )
    return normalized, saw_malformed_call

def _execute_tool_message(
    dispatch: dict[str, Any],
    tool_call: dict[str, Any],
) -> dict[str, Any]:
    """执行一条 tool call，并包装为标准 tool message。"""
    name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])

    tool_fn = dispatch.get(name)
    if tool_fn is None:
        name_lower = name.lower()
        for key in dispatch:
            if key.lower() == name_lower:
                tool_fn = dispatch[key]
                break

    if tool_fn is None:
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(
                {"status": "error", "message": f"Unknown tool: {name}"},
                ensure_ascii=False,
            ),
        }

    try:
        sig = inspect.signature(tool_fn)
        accepted = {
            param_name
            for param_name, param in sig.parameters.items()
            if param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        arguments = {
            key: value for key, value in arguments.items() if key in accepted
        }
    except (TypeError, ValueError):
        pass

    result = tool_fn(**arguments)
    return {
        "role": "tool",
        "tool_call_id": tool_call["id"],
        "content": json.dumps(result, ensure_ascii=False),
    }


def run_rollout(
    model,
    tokenizer,
    messages: list[dict],
    tools: list[dict],
    max_tool_rounds: int = 5,
    case: BenchmarkCase | None = None,
) -> RolloutTrace:
    """
    执行一条完整的 multi-turn rollout。

    注意：
    - assistant token 会被保留给 trainer 计算 GRPO loss
    - tool message 只参与环境状态推进与 reward 判定，不直接计入 policy loss
    """
    # case 级配置优先于全局 rollout 配置，便于对高风险样本做更保守的搜索。
    effective_max_tool_rounds = case.rlvr_max_tool_rounds if case and case.rlvr_max_tool_rounds is not None else max_tool_rounds

    history = list(messages)
    dispatch = _TOOL_DISPATCH
    assistant_turns: list[AssistantTurnTrace] = []
    tool_messages: list[dict[str, Any]] = []
    termination_reason = "no_tool_call"

    tool_round = 0
    while True:
        # policy 先基于当前 history 生成一个 assistant turn。
        assistant_text, token_ids, logprobs = _generate_assistant_turn(
            model=model,
            tokenizer=tokenizer,
            messages=history,
            tools=tools,
        )
        normalized_tool_calls, saw_malformed_tool_call = _normalize_tool_calls(assistant_text)

        if not normalized_tool_calls:
            # 没有可执行的工具调用时，区分“自然结束”和“模型试图调工具但格式坏了”。
            history.append({"role": "assistant", "content": assistant_text})
            assistant_turns.append(
                AssistantTurnTrace(
                    assistant_text=assistant_text,
                    token_ids=token_ids,
                    logprobs=logprobs,
                    tool_calls=[],
                    tool_messages=[],
                )
            )
            termination_reason = "malformed_tool_call" if saw_malformed_tool_call else "no_tool_call"
            break

        assistant_message = {
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": normalized_tool_calls,
        }
        history.append(assistant_message)

        current_tool_messages: list[dict[str, Any]] = []
        for tool_call in normalized_tool_calls:
            # tool result 会进入 history，影响下一轮生成，
            # 但不会作为 GRPO 的直接优化 token。
            tool_message = _execute_tool_message(dispatch, tool_call)
            history.append(tool_message)
            tool_messages.append(tool_message)
            current_tool_messages.append(tool_message)

        assistant_turns.append(
            AssistantTurnTrace(
                assistant_text=assistant_text,
                token_ids=token_ids,
                logprobs=logprobs,
                tool_calls=normalized_tool_calls,
                tool_messages=current_tool_messages,
            )
        )

        tool_round += 1
        if tool_round >= effective_max_tool_rounds:
            # 达到最大轮数通常意味着策略没有高效收敛，后续 reward 会对其惩罚。
            # 追加一个空 assistant 终态，占位为“未收敛结束”，避免 history 以 tool message 收尾。
            # 这条终态消息不是模型真正生成的一轮 assistant，因此不会写入 assistant_turns，
            # 也不会进入 GRPO loss 的 token 展平结果。
            # 它故意保持空内容，使 benchmark 的 S5 在 max_rounds 场景下预期为 0.0。
            history.append({"role": "assistant", "content": ""})
            termination_reason = "max_rounds"
            break

    return RolloutTrace(
        assistant_turns=assistant_turns,
        tool_messages=tool_messages,
        message_history=history,
        termination_reason=termination_reason,
    )
