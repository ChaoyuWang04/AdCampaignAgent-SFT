#!/usr/bin/env python3
# coding: utf-8
"""
统一 LoRA SFT 训练脚本，支持 all_assistant 和 last_assistant_only 两种模式。
"""

import argparse
import json
import os
from typing import Any, Dict, List, Optional

import torch
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainerCallback,
    TrainingArguments,
    set_seed,
    EarlyStoppingCallback,
)

try:
    from transformers import BitsAndBytesConfig
    _HAS_BNB = True
except Exception:
    _HAS_BNB = False

try:
    from peft import prepare_model_for_kbit_training
    _HAS_KBIT_PREP = True
except Exception:
    _HAS_KBIT_PREP = False

if __package__ in {None, ""}:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common.project_paths import default_model_dir
from src.train.inspect_qwen_dataset import DataCollatorForCausal, JsonlConversations


# ─── Callback ─────────────────────────────────────────────────

class ConsoleLossCallback(TrainerCallback):
    """实时打印 loss / lr，可选写入日志文件。"""

    def __init__(self, log_file: str = "") -> None:
        super().__init__()
        self._fh = None
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            self._fh = open(log_file, "a", encoding="utf-8")

    def on_log(self, args, state, control, logs=None, **kwargs):
        if not logs:
            return
        step = state.global_step
        loss = logs.get("loss", logs.get("train_loss"))
        lr   = logs.get("learning_rate")
        msg  = f"step={step}"
        if loss is not None: msg += f" | loss={loss:.6f}"
        if lr   is not None: msg += f" | lr={lr:.6e}"
        print(msg, flush=True)
        if self._fh:
            self._fh.write(msg + "\n")
            self._fh.flush()

    def on_train_end(self, args, state, control, **kwargs):
        if self._fh:
            try:
                self._fh.close()
            except Exception:
                pass


# ─── Args ─────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="统一 LoRA SFT 训练脚本（all_assistant / last_assistant_only）"
    )

    # 数据与模型
    parser.add_argument("--train_file",          type=str, required=True)
    parser.add_argument("--eval_file",           type=str, default="")
    parser.add_argument("--model_name_or_path",  type=str, default=str(default_model_dir()))
    parser.add_argument("--output_dir",          type=str, default="./qwen_lora_output")

    # 核心开关
    parser.add_argument(
        "--only_last_assistant", action="store_true",
        help="只对最后一条 assistant 回复计算 loss；不加此参数则对所有 assistant 回复计算 loss",
    )
    parser.add_argument(
        "--full_ft", action="store_true",
        help="全参数微调，不使用 LoRA；默认为 LoRA 模式"
    )

    # 序列长度
    parser.add_argument("--max_seq_length",      type=int,   default=4096)
    parser.add_argument("--local_files_only",    action="store_true")

    # 训练超参
    parser.add_argument("--learning_rate",       type=float, default=2e-5)
    parser.add_argument("--num_train_epochs",    type=float, default=2.0)
    parser.add_argument("--warmup_ratio",        type=float, default=0.03)
    parser.add_argument("--weight_decay",        type=float, default=0.0)
    parser.add_argument("--max_steps",           type=int,   default=-1)
    parser.add_argument("--lr_scheduler_type",   type=str,   default="cosine")

    # Batch / 梯度
    parser.add_argument("--per_device_train_batch_size",  type=int, default=1)
    parser.add_argument("--per_device_eval_batch_size",   type=int, default=1)
    parser.add_argument("--gradient_accumulation_steps",  type=int, default=8)

    # 日志 / 保存 / Eval
    parser.add_argument("--logging_steps",           type=int, default=10)
    parser.add_argument("--save_steps",              type=int, default=200)
    parser.add_argument("--save_total_limit",        type=int, default=10)
    parser.add_argument("--eval_steps",              type=int, default=100)
    parser.add_argument("--eval_accumulation_steps", type=int, default=4)
    parser.add_argument("--log_file",                type=str, default="")

    # 精度 / 显存
    parser.add_argument("--bf16",                   action="store_true")
    parser.add_argument("--fp16",                   action="store_true")
    parser.add_argument("--gradient_checkpointing", action="store_true")
    parser.add_argument("--qlora",                  action="store_true")

    # 其他
    parser.add_argument("--dataloader_num_workers",  type=int, default=2)
    parser.add_argument("--seed",                    type=int, default=42)
    parser.add_argument("--tools_file",              type=str, default="")
    parser.add_argument("--tools_json",              type=str, default="")
    parser.add_argument("--early_stopping_patience", type=int, default=0,
        help="eval loss 连续多少次不下降就停止；0 表示关闭")
    parser.add_argument("--early_stopping_threshold", type=float, default=0.001,
        help="eval loss 下降幅度小于此值视为没有改善")

    # LoRA
    parser.add_argument("--lora_r",        type=int,   default=32)
    parser.add_argument("--lora_alpha",    type=int,   default=64)
    parser.add_argument("--lora_dropout",  type=float, default=0.05)
    parser.add_argument(
        "--target_modules", type=str,
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
    )

    return parser.parse_args()


# ─── Helpers ──────────────────────────────────────────────────

def load_default_tools(args: argparse.Namespace) -> Optional[List[Dict[str, Any]]]:
    if args.tools_file:
        with open(args.tools_file, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if not isinstance(obj, list):
            raise ValueError("tools_file must contain a JSON array")
        return obj
    if args.tools_json:
        obj = json.loads(args.tools_json)
        if not isinstance(obj, list):
            raise ValueError("tools_json must be a JSON array")
        return obj
    return None


def build_lora_model(base_model, args: argparse.Namespace):
    target_modules = [m.strip() for m in args.target_modules.split(",") if m.strip()]
    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    model = get_peft_model(base_model, lora_cfg)
    model.print_trainable_parameters()
    return model


# ─── Main ─────────────────────────────────────────────────────

def main():
    args = parse_args()
    set_seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    mode_label = "last_assistant_only" if args.only_last_assistant else "all_assistant"
    print(f"Training mode: {mode_label}")

    # 精度
    torch_dtype = (
        torch.bfloat16 if args.bf16 else
        torch.float16  if args.fp16 else
        torch.float32
    )

    # Tokenizer
    print(f"Loading tokenizer: {args.model_name_or_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name_or_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # 模型加载参数
    load_kwargs: Dict[str, Any] = {
        "trust_remote_code":  True,
        "local_files_only":   args.local_files_only,
    }
    if args.qlora:
        if not _HAS_BNB:
            raise RuntimeError("bitsandbytes is required for QLoRA.")
        if not _HAS_KBIT_PREP:
            raise RuntimeError("prepare_model_for_kbit_training unavailable. Upgrade peft.")
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if args.bf16 else torch.float16,
        )
        load_kwargs["device_map"] = "auto"
    else:
        load_kwargs["dtype"] = torch_dtype

    # 加载模型
    print(f"Loading base model: {args.model_name_or_path}")
    model = AutoModelForCausalLM.from_pretrained(args.model_name_or_path, **load_kwargs)

    if args.qlora:
        model = prepare_model_for_kbit_training(model)

    # gradient_checkpointing 必须在 build_lora_model 之前
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        if hasattr(model, "config"):
            model.config.use_cache = False

    if args.full_ft and args.qlora:
        raise ValueError("--full_ft 和 --qlora 不能同时使用")

    if args.full_ft:
        for param in model.parameters():
            param.requires_grad_(True)
        print("Mode: Full fine-tuning (all parameters)")
    else:
        model = build_lora_model(model, args)
        print(f"Mode: LoRA fine-tuning")

    # 工具列表
    default_tools = load_default_tools(args)

    # 数据集
    def make_dataset(path: str) -> JsonlConversations:
        return JsonlConversations(
            path,
            tokenizer,
            args.max_seq_length,
            only_last_assistant=args.only_last_assistant,  # ← 唯一的核心开关
            default_tools=default_tools,
        )

    print(f"Loading train dataset: {args.train_file}")
    train_dataset = make_dataset(args.train_file)
    print(f"Train size: {len(train_dataset)} samples")

    eval_dataset = None
    if args.eval_file:
        eval_dataset = make_dataset(args.eval_file)
        print(f"Eval size: {len(eval_dataset)} samples")

    # TrainingArguments
    training_args = TrainingArguments(
        output_dir=args.output_dir,

        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        max_steps=args.max_steps,

        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        num_train_epochs=args.num_train_epochs,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type=args.lr_scheduler_type,

        logging_steps=args.logging_steps,
        logging_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,

        eval_strategy="steps" if eval_dataset is not None else "no",
        eval_steps=args.eval_steps,
        eval_accumulation_steps=args.eval_accumulation_steps,

        optim="paged_adamw_8bit" if args.qlora else "adamw_torch",
        bf16=args.bf16,
        fp16=args.fp16 and not args.bf16,

        dataloader_num_workers=args.dataloader_num_workers,
        report_to=["wandb"],
        remove_unused_columns=False,
        seed=args.seed,

        load_best_model_at_end=eval_dataset is not None,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        data_collator=DataCollatorForCausal(tokenizer=tokenizer),
        callbacks=[
            ConsoleLossCallback(args.log_file),
            *(
                [EarlyStoppingCallback(
                    early_stopping_patience=args.early_stopping_patience,
                    early_stopping_threshold=args.early_stopping_threshold,
                )]
                if args.early_stopping_patience > 0 else []
            ),
        ],
    )

    trainer.train()
    trainer.save_state()
    trainer.save_model(args.output_dir)
    print(f"Training complete [{mode_label}]. Adapter saved to: {args.output_dir}")


if __name__ == "__main__":
    main()