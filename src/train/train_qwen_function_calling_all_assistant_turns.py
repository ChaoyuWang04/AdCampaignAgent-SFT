#!/usr/bin/env python3
# coding: utf-8
"""
Function Calling LoRA SFT for Qwen models.
对每条对话中的所有 assistant 回复计算 loss，适合训练工具调用轨迹。

这个脚本的目标和 benchmark 更一致：
  1. 中间的 assistant tool call 参与 loss
  2. 最后的 assistant 总结也参与 loss
  3. 可选启用 QLoRA，但默认就是普通 LoRA，而不是全参数训练
"""

import argparse
import json
import os
from typing import Optional, List, Dict, Any

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
    TrainerCallback,
)

try:
    from transformers import BitsAndBytesConfig
    _HAS_BNB = True
except Exception:
    _HAS_BNB = False

from peft import LoraConfig, get_peft_model

try:
    from peft import prepare_model_for_kbit_training
    _HAS_KBIT_PREP = True
except Exception:
    _HAS_KBIT_PREP = False

if __package__ in {None, ""}:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common.project_paths import default_model_dir
from src.train.inspect_qwen_dataset import JsonlConversations, DataCollatorForCausal


class ConsoleLossCallback(TrainerCallback):
    """在终端实时打印 loss / lr，并可选写入日志文件。"""

    def __init__(self, log_file: str = "") -> None:
        super().__init__()
        self.log_file = log_file
        self._fh = None
        if self.log_file:
            log_dir = os.path.dirname(self.log_file)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            self._fh = open(self.log_file, "a", encoding="utf-8")

    def on_log(self, args, state, control, logs=None, **kwargs):
        """每次 Trainer 写日志时触发。"""
        if not logs:
            return
        step = state.global_step
        loss = logs.get("loss", logs.get("train_loss"))
        lr = logs.get("learning_rate")
        msg = f"step={step}"
        if loss is not None:
            msg += f" | loss={loss:.6f}"
        if lr is not None:
            msg += f" | lr={lr:.6e}"
        print(msg, flush=True)
        if self._fh is not None:
            self._fh.write(msg + "\n")
            self._fh.flush()

    def on_train_end(self, args, state, control, **kwargs):
        """训练结束时关闭日志文件。"""
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    """定义命令行参数。"""
    parser = argparse.ArgumentParser(
        description="LoRA fine-tuning for Qwen function-calling with loss on all assistant turns"
    )

    parser.add_argument("--train_file", type=str, required=True, help="训练数据文件路径（JSON/JSONL）")
    parser.add_argument("--model_name_or_path", type=str, default=str(default_model_dir()), help="基础模型路径")
    parser.add_argument("--output_dir", type=str, default="./qwen_function_calling_lora")

    parser.add_argument("--max_seq_length", type=int, default=4096)
    parser.add_argument("--local_files_only", action="store_true", help="只从本地加载模型和 tokenizer")

    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--max_steps", type=int, default=-1, help="最大训练步数，-1 表示由 epoch 决定")
    parser.add_argument("--weight_decay", type=float, default=0.0)
    parser.add_argument("--num_train_epochs", type=float, default=3.0)
    parser.add_argument("--warmup_ratio", type=float, default=0.03)
    parser.add_argument("--eval_file", type=str, default="", help="测试集路径，为空则不做 eval")
    parser.add_argument("--eval_steps", type=int, default=100, help="eval 触发间隔")
    parser.add_argument("--per_device_train_batch_size", type=int, default=1)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=8)
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--save_steps", type=int, default=1000)
    parser.add_argument("--save_total_limit", type=int, default=3)
    parser.add_argument("--lr_scheduler_type", type=str, default="cosine")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--gradient_checkpointing", action="store_true")
    parser.add_argument("--dataloader_num_workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log_file", type=str, default="", help="可选：loss 日志输出文件")

    parser.add_argument("--tools_file", type=str, default="", help="全局工具列表 JSON 文件")
    parser.add_argument("--tools_json", type=str, default="", help="内联工具列表 JSON 字符串")

    parser.add_argument("--qlora", action="store_true", help="启用 4-bit QLoRA")
    parser.add_argument("--lora_r", type=int, default=32)
    parser.add_argument("--lora_alpha", type=int, default=64)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument(
        "--target_modules",
        type=str,
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
        help="要插入 LoRA adapter 的模块名称"
    )

    return parser.parse_args()


def build_lora_model(base_model, args: argparse.Namespace):
    """在基础模型上插入 LoRA adapter。"""
    target_modules = [m.strip() for m in args.target_modules.split(",") if m.strip()]
    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=target_modules,
    )
    lora_model = get_peft_model(base_model, lora_cfg)
    lora_model.print_trainable_parameters()
    return lora_model


def load_default_tools(args: argparse.Namespace) -> Optional[List[Dict[str, Any]]]:
    """加载全局默认工具列表，用于补齐样本里缺失的 tools 字段。"""
    if args.tools_file:
        try:
            with open(args.tools_file, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, list):
                return obj
            raise ValueError("tools_file must contain a JSON array of tool objects")
        except Exception as e:
            raise RuntimeError(f"Failed to load tools_file: {args.tools_file}: {e}")

    if args.tools_json:
        try:
            obj = json.loads(args.tools_json)
            if isinstance(obj, list):
                return obj
            raise ValueError("tools_json must be a JSON array of tool objects")
        except Exception as e:
            raise RuntimeError(f"Failed to parse tools_json: {e}")

    return None


def main():
    """主训练流程。"""
    args = parse_args()
    set_seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    if args.bf16:
        torch_dtype = torch.bfloat16
    elif args.fp16:
        torch_dtype = torch.float16
    else:
        torch_dtype = torch.float32

    print(f"Loading tokenizer: {args.model_name_or_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name_or_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    load_kwargs = {
        "trust_remote_code": True,
        "local_files_only": args.local_files_only,
    }

    if args.qlora:
        if not _HAS_BNB:
            raise RuntimeError("bitsandbytes is required for QLoRA (install bitsandbytes first).")
        if not _HAS_KBIT_PREP:
            raise RuntimeError("prepare_model_for_kbit_training is unavailable. Upgrade peft to use QLoRA.")
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if args.bf16 else torch.float16,
        )
        load_kwargs["device_map"] = "auto"
    else:
        load_kwargs["dtype"] = torch_dtype

    print(f"Loading base model: {args.model_name_or_path}")
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name_or_path,
        **load_kwargs,
    )

    if args.qlora:
        model = prepare_model_for_kbit_training(model)

    model = build_lora_model(model, args)

    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        if hasattr(model, "config"):
            model.config.use_cache = False

    default_tools = load_default_tools(args)

    print(f"Loading dataset: {args.train_file}")
    train_dataset = JsonlConversations(
        args.train_file,
        tokenizer,
        args.max_seq_length,
        only_last_assistant=False,
        default_tools=default_tools,
    )
    print(f"Dataset size: {len(train_dataset)} samples")

    eval_dataset = None
    if args.eval_file:
        eval_dataset = JsonlConversations(
            args.eval_file,
            tokenizer,
            args.max_seq_length,
            only_last_assistant=False,
            default_tools=default_tools,
        )
        print(f"Eval dataset size: {len(eval_dataset)} samples")

    data_collator = DataCollatorForCausal(tokenizer=tokenizer)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        num_train_epochs=args.num_train_epochs,
        warmup_ratio=args.warmup_ratio,
        logging_steps=args.logging_steps,
        logging_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        eval_strategy="steps" if eval_dataset is not None else "no",
        eval_steps=args.eval_steps,
        lr_scheduler_type=args.lr_scheduler_type,
        optim="paged_adamw_8bit" if args.qlora else "adamw_torch",
        bf16=args.bf16,
        fp16=args.fp16 and not args.bf16,
        dataloader_num_workers=args.dataloader_num_workers,
        report_to=[],
        remove_unused_columns=False,
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        data_collator=data_collator,
        callbacks=[ConsoleLossCallback(args.log_file)],
    )

    trainer.train()
    trainer.save_state()
    trainer.save_model(args.output_dir)

    print("Training complete. Adapter saved to:", args.output_dir)


if __name__ == "__main__":
    main()
