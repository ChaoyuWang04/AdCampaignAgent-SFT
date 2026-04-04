#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RLVR 训练数据可视化检查脚本。

目标：
- 检查 prompt_builder 生成的 message list 是否符合预期
- 检查 rollout trace 的 message_history / token / logprob
- 检查 trainer flatten 后的 completion 是否只包含 assistant token
- 检查 prompt/completion mask 的长度与布局
- 检查 reward breakdown 与 gating 是否触发

这个脚本不加载真实模型权重，只加载 tokenizer，并使用一个可控的 mock policy
来驱动真实的 `run_rollout()`，从而把 RLVR 训练链路的关键中间态完整打印出来。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from transformers import AutoTokenizer

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_LIB = REPO_ROOT / ".venv" / "lib"
for candidate in sorted(VENV_LIB.glob("python*/site-packages")):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.project_paths import tools_schema_path
from src.rlvr.dataset import TRAIN_SPLIT, load_rlvr_cases
from src.rlvr.prompt_builder import build_case_messages
from src.rlvr.reward import compute_reward
from src.rlvr.reward_components import (
    argument_reward,
    behavior_reward,
    efficiency_penalty,
    format_reward,
    safety_reward,
    success_reward,
    tool_selection_reward,
    workflow_reward,
)
from src.rlvr.rollout import RolloutTrace, run_rollout
from src.rlvr.trainer import MultiTurnGRPOTrainer, build_trl_reward_func

try:
    from src.benchmark.benchmark_schema import BenchmarkCase
except ModuleNotFoundError:
    sys.path.append(str(REPO_ROOT / "src" / "benchmark"))
    from benchmark_schema import BenchmarkCase


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    GRAY = "\033[90m"


def color(text: str, tone: str) -> str:
    return f"{tone}{text}{C.RESET}"


def print_section(title: str) -> None:
    print()
    print(color(f"== {title} ==", C.BOLD + C.CYAN))


def truncate_text(text: str, limit: int = 200) -> str:
    text = text.replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def load_tool_schemas() -> list[dict[str, Any]]:
    payload = json.loads(tools_schema_path().read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Tool schema file must contain a JSON array.")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect RLVR training data flow.")
    parser.add_argument("--case_id", type=str, default="")
    parser.add_argument(
        "--case_type",
        type=str,
        choices=["standard", "sequential", "parallel", "oos", "clarify"],
        default="",
    )
    parser.add_argument("--model_path", type=str, default="models/Qwen3-0.6b")
    parser.add_argument("--local_files_only", action="store_true", default=True)
    return parser.parse_args()


def select_case(case_id: str, case_type: str) -> BenchmarkCase:
    cases = load_rlvr_cases(split=TRAIN_SPLIT)
    if case_id:
        for case in cases:
            if case.id == case_id:
                return case
        raise ValueError(f"Case id not found: {case_id}")
    if case_type:
        for case in cases:
            if case.case_type == case_type:
                return case
        raise ValueError(f"No train case found for case_type={case_type}")
    return cases[0]


def infer_tool_arguments(
    case: BenchmarkCase,
    tool_name: str,
    *,
    tool_index: int = 0,
) -> dict[str, Any]:
    if case.expected_tool_args and tool_name in case.expected_tool_args:
        expected_args = case.expected_tool_args[tool_name]
        if isinstance(expected_args, list):
            if tool_index < len(expected_args):
                return dict(expected_args[tool_index])
            if expected_args:
                return dict(expected_args[-1])
            return {}
        return dict(expected_args)

    context = case.context
    if tool_name == "get_campaign_metrics":
        args = {"campaign_id": context.get("campaign_id", "CMP_2048")}
        if case.case_type == "parallel":
            args["breakdown"] = "daily"
            args["date_range"] = {"start": "2026-03-01", "end": "2026-03-07"}
            args["metrics"] = ["roas", "ctr", "spend"]
            args["platform"] = ["iOS", "Android"][tool_index % 2]
        return args
    if tool_name == "validate_creative_spec":
        return {
            "file_path": context.get("file_path", "assets/mock_video.mp4"),
            "platform": context.get("platform", "Meta"),
            "ad_format": context.get("ad_format", "interstitial"),
        }
    if tool_name == "upload_creative_asset":
        return {
            "file_path": context.get("file_path", "assets/mock_video.mp4"),
            "campaign_id": context.get("campaign_id", "CMP_1024"),
            "asset_type": context.get("asset_type", "video"),
        }
    if tool_name == "search_competitor_ads":
        return {
            "competitor_name": context.get("competitor_name", "Playrix"),
            "platform": context.get("platform", "Meta"),
        }
    if tool_name == "query_knowledge_base":
        return {"query": case.user_input}
    if tool_name == "get_benchmark_data":
        return {
            "game_genre": context.get("game_genre", "casual"),
            "metric": context.get("metric", "roas_d7"),
            "region": context.get("region", "US"),
        }
    if tool_name == "get_platform_policy":
        return {
            "platform": context.get("platform", "Meta"),
            "topic": context.get("topic", "creative_spec"),
        }
    if tool_name == "detect_anomalies":
        return {"campaign_id": context.get("campaign_id", "CMP_2048")}
    if tool_name == "get_optimization_playbook":
        return {
            "issue_type": context.get("issue_type", "roas_drop"),
            "platform": context.get("platform", "Meta"),
        }
    if tool_name == "batch_upload_creatives":
        return {
            "file_paths": ["assets/mock_video_1.mp4", "assets/mock_video_2.mp4"],
            "campaign_id": context.get("campaign_id", "CMP_1024"),
        }
    return {}


def build_tool_call_text(tool_name: str, arguments: dict[str, Any]) -> str:
    return f'<tool_call>{json.dumps({"name": tool_name, "arguments": arguments}, ensure_ascii=False)}</tool_call>'


@dataclass
class MockPolicy:
    case: BenchmarkCase
    tokenizer: Any

    def forward(self, input_ids, attention_mask=None, **kwargs):
        _ = attention_mask
        _ = kwargs
        vocab_size = 256
        batch, seq = input_ids.shape
        return type("MockOutput", (), {"logits": torch.zeros(batch, seq, vocab_size)})

    def _assistant_messages_with_tools(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [m for m in messages if m.get("role") == "assistant" and m.get("tool_calls")]

    def _tool_round_index(self, messages: list[dict[str, Any]]) -> int:
        return len(self._assistant_messages_with_tools(messages))

    def _final_answer(self) -> str:
        if self.case.expected_behavior == "reject":
            return "抱歉，这属于越权或不安全请求，我不能协助执行。"
        if self.case.expected_behavior == "clarify":
            missing = self.case.required_missing_slots or ["关键信息"]
            return f"为了继续执行，我还需要你补充：{', '.join(missing)}。"
        return "我已经根据工具返回结果完成了这次任务的总结。"

    def rlvr_generate(self, *, messages, tokenizer):
        _ = tokenizer
        round_idx = self._tool_round_index(messages)

        if self.case.expected_behavior == "reject":
            text = self._final_answer()
        elif self.case.expected_behavior == "clarify":
            text = self._final_answer()
        elif self.case.case_type == "parallel":
            if round_idx == 0:
                group = self.case.expected_parallel_groups[0] if self.case.expected_parallel_groups else self.case.expected_tools
                parts = []
                for i, tool_name in enumerate(group):
                    parts.append(build_tool_call_text(tool_name, infer_tool_arguments(self.case, tool_name, tool_index=i)))
                text = "\n".join(parts)
            else:
                text = self._final_answer()
        elif self.case.case_type == "sequential":
            if round_idx < len(self.case.expected_sequence):
                tool_name = self.case.expected_sequence[round_idx]
                text = build_tool_call_text(tool_name, infer_tool_arguments(self.case, tool_name, tool_index=round_idx))
            else:
                text = self._final_answer()
        else:
            if round_idx == 0:
                tool_name = self.case.expected_tools[0] if self.case.expected_tools else "get_campaign_metrics"
                text = build_tool_call_text(tool_name, infer_tool_arguments(self.case, tool_name))
            else:
                text = self._final_answer()

        token_ids = self.tokenizer.encode(text, add_special_tokens=False) or [self.tokenizer.eos_token_id]
        # 用简单递减的假 logprob 序列，便于检查范围和边界。
        logprobs = [-(0.05 + 0.005 * (i % 7)) for i in range(len(token_ids))]
        return {
            "assistant_text": text,
            "token_ids": token_ids,
            "logprobs": logprobs,
        }


def decode_ids(tokenizer, ids: list[int]) -> str:
    return tokenizer.decode(ids, skip_special_tokens=False)


def render_role_messages(messages: list[dict[str, Any]]) -> None:
    for idx, message in enumerate(messages):
        role = color(f"[{idx:02d}] {message.get('role', 'unknown')}", C.BLUE)
        content = message.get("content", "")
        if message.get("tool_calls"):
            content = f"{truncate_text(content)} | tool_calls={truncate_text(json.dumps(message['tool_calls'], ensure_ascii=False), 160)}"
        print(f"{role}: {truncate_text(str(content), 200)}")


def format_logprob_range(logprobs: list[float]) -> str:
    if not logprobs:
        return color("empty", C.GRAY)
    return color(f"[{min(logprobs):.4f}, {max(logprobs):.4f}]", C.YELLOW)


def build_mask_layout(prompt_len: int, completion_len: int, width: int = 120) -> str:
    raw = ("P" * prompt_len) + ("C" * completion_len)
    if len(raw) <= width:
        return raw
    head = raw[: width // 2]
    tail = raw[-(width // 2) :]
    return f"{head}{color('...', C.GRAY)}{tail}"


def build_real_masks(
    *,
    trainer: MultiTurnGRPOTrainer,
    prompt_ids: list[int],
    completion_ids: list[int],
) -> tuple[torch.Tensor, torch.Tensor]:
    from trl.trainer.utils import pad

    prompt_tensor = torch.tensor(prompt_ids, dtype=torch.long)
    completion_tensor = torch.tensor(completion_ids, dtype=torch.long)
    prompt_mask = pad(
        [torch.ones_like(prompt_tensor, dtype=torch.long)],
        padding_value=0,
        padding_side="left",
    )
    completion_mask = pad(
        [torch.ones_like(completion_tensor, dtype=torch.long)],
        padding_value=0,
        padding_side="right",
    )
    _ = trainer
    return prompt_mask, completion_mask


def inspect_case(case: BenchmarkCase, tokenizer) -> None:
    tools = load_tool_schemas()
    model = MockPolicy(case=case, tokenizer=tokenizer)
    trainer = MultiTurnGRPOTrainer.for_testing(
        model=model,
        tokenizer=tokenizer,
        reward_func=build_trl_reward_func({case.id: case}),
        case_lookup={case.id: case},
        rollout_runner=run_rollout,
        num_generations=1,
        max_tool_rounds=case.rlvr_max_tool_rounds or 4,
    )

    messages = build_case_messages(case)

    print_section("Case")
    print(f"id={color(case.id, C.BOLD)} type={color(case.case_type, C.MAGENTA)} expected_behavior={color(case.expected_behavior, C.GREEN)}")
    print(f"user_input={truncate_text(case.user_input, 240)}")

    print_section("1. Prompt Tokenization")
    prompt_ids = trainer._encode_prompt_messages(messages)
    decoded_prompt = decode_ids(tokenizer, prompt_ids)
    print("原始 messages:")
    render_role_messages(messages)
    print()
    print(f"prompt token 数量: {color(str(len(prompt_ids)), C.GREEN)}")
    print(f"decode 后 prompt 预览: {truncate_text(decoded_prompt, 500)}")

    print_section("2. Rollout Trace")
    trace = run_rollout(
        model=model,
        tokenizer=tokenizer,
        messages=messages,
        tools=tools,
        max_tool_rounds=4,
        case=case,
    )
    print("完整 message_history:")
    render_role_messages(trace.message_history)
    print()
    for idx, turn in enumerate(trace.assistant_turns, start=1):
        print(
            f"assistant turn {idx}: "
            f"tokens={color(str(len(turn.token_ids)), C.GREEN)} "
            f"logprob_range={format_logprob_range(turn.logprobs)} "
            f"tool_calls={color(str(len(turn.tool_calls)), C.YELLOW)}"
        )
    print(f"termination_reason: {color(trace.termination_reason, C.RED if trace.termination_reason == 'max_rounds' else C.GREEN)}")

    print_section("3. Flatten")
    flat_ids, _, flat_text = trainer._flatten_trace(trace)
    print(f"flat completion token 数量: {color(str(len(flat_ids)), C.GREEN)}")
    print(f"flat completion decode: {truncate_text(flat_text, 600)}")
    cursor = 0
    for idx, turn in enumerate(trace.assistant_turns, start=1):
        turn_ids = flat_ids[cursor : cursor + len(turn.token_ids)]
        decoded_turn = decode_ids(tokenizer, turn_ids)
        print(color(f"--- assistant turn {idx} boundary (len={len(turn_ids)}) ---", C.MAGENTA))
        print(truncate_text(decoded_turn, 400))
        cursor += len(turn.token_ids)
    tool_texts = [str(message.get("content", "")) for message in trace.tool_messages]
    tool_leak = any(tool_text and tool_text in flat_text for tool_text in tool_texts)
    print(f"tool result token 混入 flat completion: {color(str(tool_leak), C.RED if tool_leak else C.GREEN)}")

    print_section("4. Mask")
    prompt_len = len(prompt_ids)
    completion_len = len(flat_ids)
    prompt_mask, completion_mask = build_real_masks(
        trainer=trainer,
        prompt_ids=prompt_ids,
        completion_ids=flat_ids,
    )
    print(f"prompt 长度: {color(str(prompt_len), C.GREEN)}")
    print(f"completion 长度: {color(str(completion_len), C.GREEN)}")
    print(f"prompt_mask 有效 token 数: {color(str(int(prompt_mask.sum().item())), C.GREEN)}")
    print(f"completion_mask 有效 token 数: {color(str(int(completion_mask.sum().item())), C.GREEN)}")
    print(f"mask layout: {build_mask_layout(prompt_len, completion_len)}")
    print(f"legend: {color('P', C.BLUE)}=prompt {color('C', C.YELLOW)}=completion {color('.', C.GRAY)}=padding")

    print_section("5. Reward")
    raw_format = format_reward(trace, case)
    raw_behavior = behavior_reward(trace, case)
    raw_tool_selection = tool_selection_reward(trace, case)
    raw_argument = argument_reward(trace, case)
    raw_workflow = workflow_reward(trace, case)
    raw_safety = safety_reward(trace, case)
    raw_success = success_reward(trace, case)
    raw_efficiency = efficiency_penalty(trace, case)
    reward = compute_reward(trace, case)

    reward_items = [
        ("format", reward.format, raw_format),
        ("behavior", reward.behavior, raw_behavior),
        ("tool_selection", reward.tool_selection, raw_tool_selection),
        ("argument", reward.argument, raw_argument),
        ("workflow", reward.workflow, raw_workflow),
        ("safety", reward.safety, raw_safety),
        ("success", reward.success, raw_success),
        ("efficiency", reward.efficiency, raw_efficiency),
        ("total", reward.total, reward.total),
    ]
    for name, value, raw_value in reward_items:
        suffix = ""
        if name != "total" and value != raw_value:
            suffix = color(f" (raw={raw_value:.4f})", C.GRAY)
        tone = C.RED if value < 0 else C.GREEN if value > 0.5 else C.YELLOW
        print(f"{name:>14}: {color(f'{value:.4f}', tone)}{suffix}")

    format_gating = raw_format == 0.0 and reward.behavior == 0.0 and reward.tool_selection == 0.0 and reward.argument == 0.0 and reward.workflow == 0.0 and reward.success == 0.0
    behavior_gating = raw_format != 0.0 and raw_behavior < 0.5 and (
        reward.tool_selection != raw_tool_selection
        or reward.argument != raw_argument
        or reward.workflow != raw_workflow
    )
    print()
    print(f"format gating 触发: {color(str(format_gating), C.RED if format_gating else C.GREEN)}")
    print(f"behavior gating 触发: {color(str(behavior_gating), C.RED if behavior_gating else C.GREEN)}")


def main() -> None:
    args = parse_args()
    case = select_case(args.case_id, args.case_type)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    inspect_case(case, tokenizer)


if __name__ == "__main__":
    main()
