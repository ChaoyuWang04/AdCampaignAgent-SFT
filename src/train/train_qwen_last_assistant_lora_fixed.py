#!/usr/bin/env python3
# coding: utf-8
"""
LoRA fine-tuning script for Qwen3 models.
只对每条对话的最后一条 assistant 消息计算 loss（last-assistant loss masking）。

核心思路：
  原始 LLM 训练会对所有 token 计算 loss（包括 user 的输入）。
  但我们只想让模型学会"如何回复"，不想让它学 user 的说话方式。
  所以用 label mask 把 user/system token 的 loss 屏蔽掉，只保留最后一条 assistant 的 loss。
"""

import argparse
import os
import json
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
from peft import LoraConfig, get_peft_model

# 允许直接运行此文件（不通过包导入）时也能找到 src/ 目录
if __package__ in {None, ""}:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common.project_paths import default_model_dir, processed_data_dir
from src.train.inspect_qwen_dataset import JsonlConversations, DataCollatorForCausal


# ─────────────────────────────────────────────────────────
# Callback：在终端实时打印 loss 和学习率
# ─────────────────────────────────────────────────────────
class ConsoleLossCallback(TrainerCallback):
    """
    HuggingFace Trainer 默认只把日志写到内部状态，不实时打印。
    这个 Callback 在每次 logging_steps 触发时，把 loss/lr 打印到终端。
    可选地同时写入日志文件，方便后续分析。
    """
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
        """每次 Trainer 记录日志时触发（由 logging_steps 控制频率）"""
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
        """训练结束时关闭日志文件"""
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────
# 命令行参数定义
# ─────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LoRA fine-tuning for Qwen3 (last-assistant loss only)")

    # ── 数据和模型路径 ──────────────────────────────────────
    parser.add_argument(
        "--train_file", type=str,
        default=str(processed_data_dir() / "merged_train_final_multiturn_v2.json"),
        help="训练数据文件路径（JSON/JSONL 格式）"
    )
    parser.add_argument(
        "--model_name_or_path", type=str,
        default=str(default_model_dir()),
        help="基础模型路径（本地目录或 HuggingFace model ID）"
    )
    parser.add_argument(
        "--output_dir", type=str,
        default=str(default_model_dir().parent / "qwen3-0_6b_lora_last_assistant"),
        help="训练输出目录，LoRA adapter 会保存在这里"
    )

    # ── 序列长度 ────────────────────────────────────────────
    parser.add_argument(
        "--max_seq_length", type=int, default=4096,
        help=(
            "单条样本最大 token 数。"
            "超过此长度的样本会被截断。"
            "越大显存占用越高：H200 80GB 可以跑 8192+，24GB 的卡建议 2048 以下。"
        )
    )
    parser.add_argument(
        "--local_files_only", action="store_true",
        help="只从本地加载模型，不联网。RunPod 训练时建议开启，避免意外触发下载。"
    )

    # ── 训练超参数 ──────────────────────────────────────────
    parser.add_argument(
        "--learning_rate", type=float, default=2e-4,
        help=(
            "学习率。LoRA 训练的学习率通常比全参数微调高 10x 左右。"
            "全参微调常用 2e-5，LoRA 常用 1e-4 ~ 3e-4。"
        )
    )
    parser.add_argument(
        "--max_steps", type=int, default=-1,
        help="最大训练步数。-1 表示不限制，由 num_train_epochs 决定。dry run 时设为 2。"
    )

    parser.add_argument(
        "--weight_decay", type=float, default=0.0,
        help="L2 正则化系数。LoRA 训练参数少，一般不需要正则，保持 0 即可。"
    )
    parser.add_argument(
        "--num_train_epochs", type=float, default=3.0,
        help=(
            "训练轮数。SFT 通常 1-3 轮。"
            "轮数太多会过拟合（模型死记硬背训练集）。"
        )
    )
    parser.add_argument(
        "--warmup_ratio", type=float, default=0.03,
        help=(
            "学习率 warmup 比例。"
            "训练刚开始时学习率从 0 线性增加到目标值，避免早期 loss 爆炸。"
            "0.03 表示前 3%% 的 steps 用于 warmup。"
        )
    )
    parser.add_argument(
        "--per_device_train_batch_size", type=int, default=1,
        help=(
            "每张 GPU 每次前向传播处理的样本数。"
            "LLM 训练显存紧张，通常设为 1，用 gradient_accumulation_steps 补偿。"
        )
    )
    parser.add_argument(
        "--gradient_accumulation_steps", type=int, default=8,
        help=(
            "梯度累积步数。"
            "等效 batch size = per_device_train_batch_size × gradient_accumulation_steps。"
            "这里等效 batch size = 1 × 8 = 8。"
            "作用：在显存不足时模拟大 batch 训练，每 8 步才真正更新一次权重。"
        )
    )
    parser.add_argument("--logging_steps", type=int, default=10, help="每隔多少步打印一次 loss")
    parser.add_argument("--save_steps", type=int, default=1000, help="每隔多少步保存一次 checkpoint")
    parser.add_argument(
        "--save_total_limit", type=int, default=3,
        help="最多保留多少个 checkpoint，旧的自动删除，避免磁盘占满"
    )
    parser.add_argument(
        "--lr_scheduler_type", type=str, default="cosine",
        help=(
            "学习率调度策略。"
            "cosine：学习率按余弦曲线从峰值平滑降到接近 0，是 LLM 训练的标准选择。"
        )
    )

    # ── 精度和显存优化 ──────────────────────────────────────
    parser.add_argument(
        "--bf16", action="store_true",
        help=(
            "使用 bfloat16 精度训练。"
            "相比 float32 节省一半显存，且比 fp16 数值更稳定（不容易溢出）。"
            "H100/H200 原生支持 bf16，强烈推荐开启。"
        )
    )
    parser.add_argument(
        "--fp16", action="store_true",
        help="使用 float16 精度。老一代 GPU（V100/T4）用 fp16，新卡优先 bf16。"
    )
    parser.add_argument(
        "--gradient_checkpointing", action="store_true",
        help=(
            "梯度检查点。"
            "正常训练会把所有中间激活值保存在显存里用于反向传播，非常占显存。"
            "开启后只保存关键节点，其余在反向传播时重新计算，用计算换显存。"
            "显存节省约 30-40%%，训练速度降低约 20%%。"
        )
    )

    # ── 其他 ────────────────────────────────────────────────
    parser.add_argument("--dataloader_num_workers", type=int, default=2, help="数据加载并行进程数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子，保证实验可复现")
    parser.add_argument("--log_file", type=str, default="", help="可选：将 loss 日志写入此文件")
    parser.add_argument("--tools_file", type=str, default="", help="工具列表 JSON 文件路径（OpenAI/Qwen schema）")
    parser.add_argument("--tools_json", type=str, default="", help="工具列表 JSON 字符串（内联传入）")

    # ── LoRA 配置 ────────────────────────────────────────────
    parser.add_argument(
        "--lora_r", type=int, default=32,
        help=(
            "LoRA 秩（rank）。"
            "LoRA 原理：把大矩阵的更新分解为两个小矩阵相乘（A × B），r 是小矩阵的中间维度。"
            "r 越大，可学习参数越多，表达能力越强，但显存也越大。"
            "常用值：8（极轻）、16、32（均衡）、64（重）。"
        )
    )
    parser.add_argument(
        "--lora_alpha", type=int, default=64,
        help=(
            "LoRA 缩放系数。实际学习率缩放比例 = lora_alpha / lora_r。"
            "这里 64/32 = 2，是常见的 alpha = 2×r 设置。"
        )
    )
    parser.add_argument(
        "--lora_dropout", type=float, default=0.05,
        help="LoRA 层的 dropout 率，轻微防止过拟合"
    )
    parser.add_argument(
        "--target_modules", type=str,
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
        help=(
            "要插入 LoRA adapter 的模块名称。"
            "q/k/v/o_proj：Attention 层的 QKV 投影和输出投影。"
            "gate/up/down_proj：FFN（前馈网络）层。"
            "覆盖所有投影层是目前 SFT 的标准做法。"
        )
    )

    return parser.parse_args()


# ─────────────────────────────────────────────────────────
# 构建 LoRA 模型
# ─────────────────────────────────────────────────────────
def build_lora_model(base_model, args: argparse.Namespace):
    """
    在 base_model 的指定层插入 LoRA adapter。
    
    LoRA 原理简述：
      原始权重矩阵 W（冻结，不更新）
      额外插入两个小矩阵 A、B（可训练）
      前向传播：output = W·x + (B·A)·x × (alpha/r)
      只训练 A、B，参数量从亿级降到百万级。
    """
    target_modules = [m.strip() for m in args.target_modules.split(",") if m.strip()]
    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",          # 不训练 bias，节省参数
        task_type="CAUSAL_LM", # 因果语言模型（GPT 类）
        target_modules=target_modules,
    )
    lora_model = get_peft_model(base_model, lora_cfg)
    # 打印可训练参数量，验证 LoRA 是否生效（应该只有几百万，而不是几十亿）
    lora_model.print_trainable_parameters()
    return lora_model


# ─────────────────────────────────────────────────────────
# 主训练流程
# ─────────────────────────────────────────────────────────
def main():
    args = parse_args()

    # 设置随机种子，确保 dropout/数据shuffle 等随机操作可复现
    set_seed(args.seed)
    os.makedirs(args.output_dir, exist_ok=True)

    # ── 1. 确定训练精度 ──────────────────────────────────────
    # 在加载模型前就确定 dtype，避免先用 float32 加载再转换（浪费显存和时间）
    if args.bf16:
        torch_dtype = torch.bfloat16   # H100/H200 首选
    elif args.fp16:
        torch_dtype = torch.float16    # 老卡备选
    else:
        torch_dtype = torch.float32    # 默认，显存占用最大

    # ── 2. 加载 Tokenizer ───────────────────────────────────
    print(f"Loading tokenizer: {args.model_name_or_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name_or_path,
        trust_remote_code=True,         # Qwen 有自定义代码，需要信任
        local_files_only=args.local_files_only,
    )
    # Qwen3 的 pad_token 可能未设置，用 eos_token 代替
    # pad_token 用于 batch 内对齐不同长度的序列
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    # right padding：在序列右侧补 pad，与 causal LM 的注意力掩码兼容
    tokenizer.padding_side = "right"

    # ── 3. 加载基础模型 ─────────────────────────────────────
    print(f"Loading base model: {args.model_name_or_path}")
    model = AutoModelForCausalLM.from_pretrained(
        args.model_name_or_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
        dtype=torch_dtype,        # 【修复】直接用目标精度加载，避免二次转换
    )

    # ── 4. 插入 LoRA adapter ────────────────────────────────
    # 必须在开启 gradient_checkpointing 之前完成，
    # 否则 checkpointing 的 hook 可能与 LoRA 的 hook 冲突
    model = build_lora_model(model, args)

    # ── 5. 开启梯度检查点（显存优化）──────────────────────────
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        # gradient_checkpointing 与 KV cache 不兼容：
        # KV cache 是推理时的优化，训练时必须关闭
        if hasattr(model, "config"):
            model.config.use_cache = False

    # ── 6. 加载工具列表（可选）─────────────────────────────
    # 如果数据集中某些样本没有 tools 字段，用这里的全局 tools 补充
    default_tools: Optional[List[Dict[str, Any]]] = None
    if args.tools_file:
        try:
            with open(args.tools_file, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, list):
                default_tools = obj
            else:
                raise ValueError("tools_file must contain a JSON array of tool objects")
        except Exception as e:
            raise RuntimeError(f"Failed to load tools_file: {args.tools_file}: {e}")
    elif args.tools_json:
        try:
            obj = json.loads(args.tools_json)
            if isinstance(obj, list):
                default_tools = obj
            else:
                raise ValueError("tools_json must be a JSON array of tool objects")
        except Exception as e:
            raise RuntimeError(f"Failed to parse tools_json: {e}")

    # ── 7. 加载数据集 ────────────────────────────────────────
    # JsonlConversations 会把对话格式化为模型输入，
    # 并用 only_last_assistant=True 屏蔽非最后一条 assistant 的 loss
    print(f"Loading dataset: {args.train_file}")
    train_dataset = JsonlConversations(
        args.train_file,
        tokenizer,
        args.max_seq_length,
        only_last_assistant=True,   # 只对最后一条 assistant 回复计算 loss
        default_tools=default_tools,
    )
    print(f"Dataset size: {len(train_dataset)} samples")

    # DataCollator：把多条样本拼成一个 batch，处理 padding 和 label mask
    data_collator = DataCollatorForCausal(tokenizer=tokenizer)

    # ── 8. 定义训练参数 ─────────────────────────────────────
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
        lr_scheduler_type=args.lr_scheduler_type,
        optim="adamw_torch",            # AdamW 是 LLM 训练的标准优化器
        bf16=args.bf16,
        fp16=args.fp16 and not args.bf16,  # bf16 和 fp16 互斥，bf16 优先
        dataloader_num_workers=args.dataloader_num_workers,
        report_to=[],                   # 不上报到 wandb/tensorboard（可按需开启）
        remove_unused_columns=False,    # 保留数据集中的所有列（包括 label mask）
        seed=args.seed         
    )

    # ── 9. 初始化 Trainer 并开始训练 ────────────────────────
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        processing_class=tokenizer,     # 【修复】新版 transformers 已将 tokenizer 参数改名
        data_collator=data_collator,
        callbacks=[ConsoleLossCallback(args.log_file)],  # 【修复】移除了永远为真的 `or True`
    )

    trainer.train()

    # ── 10. 保存训练结果 ─────────────────────────────────────
    # save_state：保存 optimizer state、scheduler state、随机状态等，用于断点续训
    trainer.save_state()
    # save_model：保存 LoRA adapter 权重（不是完整模型，只有几百MB）
    trainer.save_model(args.output_dir)

    print("Training complete. Adapter saved to:", args.output_dir)


if __name__ == "__main__":
    main()