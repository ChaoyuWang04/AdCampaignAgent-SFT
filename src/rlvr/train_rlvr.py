#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RLVR / multi-turn GRPO 的最小训练入口。

职责：
- 解析 CLI 参数
- 加载 benchmark case split
- 加载 tokenizer 与 tool schema
- 构造 `GRPOConfig`
- 初始化 `MultiTurnGRPOTrainer`
- 启动训练并保存 checkpoint

当前目标不是性能最优，而是先把
`case -> rollout -> reward -> GRPO update -> checkpoint`
整条链路跑通。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_LIB = REPO_ROOT / ".venv" / "lib"
for candidate in sorted(VENV_LIB.glob("python*/site-packages")):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from transformers import AutoTokenizer

from src.common.project_paths import tools_schema_path
from src.rlvr.dataset import EVAL_SPLIT, TRAIN_SPLIT, load_rlvr_cases
from src.rlvr.trainer import (
    GRPOConfig,
    MultiTurnGRPOTrainer,
    build_train_dataset,
    build_trl_reward_func,
)


def parse_args() -> argparse.Namespace:
    """定义当前 MVP / smoke 阶段所需的训练参数。"""
    parser = argparse.ArgumentParser(description="Train multi-turn RLVR with TRL GRPO.")
    parser.add_argument("--model_path", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--max_steps", type=int, default=20)
    parser.add_argument("--num_generations", type=int, default=4)
    parser.add_argument("--max_tool_rounds", type=int, default=4)
    parser.add_argument("--per_device_train_batch_size", type=int, default=1)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=8)
    parser.add_argument("--learning_rate", type=float, default=1e-6)
    parser.add_argument("--beta", type=float, default=0.01)
    parser.add_argument("--max_completion_length", type=int, default=256)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for training/sampling. RLVR train/eval split is loaded from precomputed directories.",
    )
    parser.add_argument("--tools_file", type=str, default=str(tools_schema_path()))
    parser.add_argument("--use_peft", action="store_true")
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--local_files_only", action="store_true")
    return parser.parse_args()


def load_tool_schemas(path: str) -> list[dict]:
    """读取工具 schema，传给 chat template 与 rollout。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Tool schema file must contain a JSON array.")
    return payload


def maybe_build_peft_config(args: argparse.Namespace):
    """按需构造 LoRA 配置；CPU smoke 默认不启用。"""
    if not args.use_peft:
        return None
    from peft import LoraConfig

    return LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )


def main() -> None:
    """训练入口主流程。"""
    args = parse_args()

    train_cases = load_rlvr_cases(split=TRAIN_SPLIT)
    eval_cases = load_rlvr_cases(split=EVAL_SPLIT)
    case_lookup = {case.id: case for case in train_cases + eval_cases}

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    train_dataset = build_train_dataset(train_cases)
    reward_func = build_trl_reward_func(case_lookup)
    tool_schemas = load_tool_schemas(args.tools_file)

    config = GRPOConfig(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        max_steps=args.max_steps,
        num_generations=args.num_generations,
        # generation_batch_size 必须与 num_generations 对齐，否则 TRL 无法按 group 组织样本。
        generation_batch_size=args.num_generations,
        max_completion_length=args.max_completion_length,
        temperature=args.temperature,
        beta=args.beta,
        epsilon=0.2,
        num_iterations=1,
        # 当前 trainer 的 advantage 逻辑按 GRPO 的 group normalization 实现。
        loss_type="grpo",
        report_to="none",
        remove_unused_columns=False,
        save_strategy="steps",
        save_steps=max(1, args.max_steps),
        eval_strategy="no",
        seed=args.seed,
        bf16=args.bf16,
        fp16=args.fp16,
    )

    trainer = MultiTurnGRPOTrainer(
        model=args.model_path,
        args=config,
        train_dataset=train_dataset,
        processing_class=tokenizer,
        reward_funcs=[reward_func],
        reward_processing_classes=None,
        case_lookup=case_lookup,
        max_tool_rounds=args.max_tool_rounds,
        tool_schemas=tool_schemas,
        peft_config=maybe_build_peft_config(args),
    )
    trainer.train()
    trainer.save_model(args.output_dir)


if __name__ == "__main__":
    main()
