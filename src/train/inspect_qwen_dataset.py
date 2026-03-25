#!/usr/bin/env python3
# coding: utf-8
"""
数据集检查与训练数据构造模块。

核心功能：
  1. JsonlConversations：读取 JSON/JSONL 格式的多轮对话数据，
     将每条对话模板化为 token 序列，并构造 loss mask
     （只让模型在 assistant 的回复上学习，忽略 user/system 的输入）。

  2. DataCollatorForCausal：将变长样本对齐成 batch，供 Trainer 使用。

  3. main()：命令行可视化工具，用于检查数据处理是否正确。

关键设计：前缀差分法定位 assistant token 区间
  对完整 messages 做一次模板化，得到 full_ids（总长 N）。
  再对 messages[:1], messages[:2], ... 分别模板化，通过长度差分
  确定每条消息在 full_ids 中的 [start, end) 区间。
  只将 assistant 角色的区间标记为 loss=True，其余置为 -100（忽略）。
"""

import argparse
import json
import os
import inspect as _inspect
from typing import List, Tuple, Any, Dict, Optional

import torch
from transformers import AutoTokenizer

if __package__ in {None, ""}:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common.project_paths import default_model_dir, processed_data_dir, tools_schema_path


# ──────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────

def _supports_tools_kw(tokenizer: AutoTokenizer) -> bool:
    """
    检测分词器的 apply_chat_template 是否支持 tools 关键字参数。
    Qwen3 的聊天模板支持将工具描述（函数签名）注入 system prompt，
    使模型知道可以调用哪些工具。老版本分词器没有这个能力。
    """
    try:
        sig = _inspect.signature(tokenizer.apply_chat_template)
        return any(p.name == "tools" for p in sig.parameters.values())
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────
# 数据集类
# ──────────────────────────────────────────────────────────────────

class JsonlConversations:
    """
    多轮对话数据集，适配 Qwen 聊天模板。

    输入格式（JSON array 或 JSONL，每条样本）：
      {
        "messages": [
          {"role": "system",    "content": "..."},
          {"role": "user",      "content": "..."},
          {"role": "assistant", "content": "..."},
          ...
        ],
        "tools": [...]  // 可选，工具描述数组
      }

    输出（__getitem__ 返回）：
      {
        "input_ids":      LongTensor[seq_len]  -- token id 序列
        "attention_mask": LongTensor[seq_len]  -- 全 1（无 padding）
        "labels":         LongTensor[seq_len]  -- loss 目标，非 assistant 区域为 -100
      }

    -100 是 PyTorch CrossEntropyLoss 的忽略索引，
    被置为 -100 的位置不会参与 loss 计算，
    即模型只在 assistant 回复的 token 上学习。
    """

    def __init__(
        self,
        path: str,
        tokenizer: AutoTokenizer,
        max_seq_length: int,
        only_last_assistant: bool = False,
        default_tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        参数：
          path               -- 数据文件路径
          tokenizer          -- HuggingFace 分词器
          max_seq_length     -- 超过此长度从头部截断（保留对话尾部）
          only_last_assistant-- True：只对最后一条 assistant 计算 loss
                                False：对所有 assistant 回复计算 loss
          default_tools      -- 全局工具列表，注入到没有 tools 字段的样本
        """
        self.tokenizer = tokenizer
        self.max_seq_length = max_seq_length
        self.only_last_assistant = only_last_assistant
        self.examples: List[Dict[str, Any]] = []
        self._default_tools: Optional[List[Dict[str, Any]]] = (
            default_tools
            if isinstance(default_tools, list) and len(default_tools) > 0
            else None
        )

        def _normalize_obj(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """
            统一数据格式：
            支持 messages 或 conversation 字段名，
            统一输出为 {"messages": [...], "tools": [...]}。
            """
            if not isinstance(obj, dict):
                return None
            msgs = None
            if isinstance(obj.get("messages"), list):
                msgs = obj["messages"]
            elif isinstance(obj.get("conversation"), list):
                msgs = obj["conversation"]
            if msgs is None:
                return None
            new_obj: Dict[str, Any] = {"messages": msgs}
            if isinstance(obj.get("tools"), list):
                new_obj["tools"] = obj["tools"]
            elif self._default_tools is not None:
                # 没有 tools 字段的样本，注入全局默认工具列表
                new_obj["tools"] = self._default_tools
            return new_obj

        # 读取文件：优先尝试 JSON array，回退 JSONL
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        stripped = content.lstrip()
        parsed_any = False

        if stripped.startswith("["):
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    for raw in data:
                        norm = _normalize_obj(raw)
                        if norm is not None:
                            self.examples.append(norm)
                    parsed_any = len(self.examples) > 0
            except Exception:
                parsed_any = False

        if not parsed_any:
            print(f"Failed to parse JSON array, trying JSONL: {path}")
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except Exception:
                        continue
                    norm = _normalize_obj(raw)
                    if norm is not None:
                        self.examples.append(norm)

        if len(self.examples) == 0:
            raise ValueError(
                "No valid samples found. "
                "Expect JSON array or JSONL with objects containing "
                "a 'messages' or 'conversation' list."
            )

        # 检测分词器是否支持 tools 参数（只检测一次）
        self._use_tools_kw = _supports_tools_kw(self.tokenizer)

    def __len__(self) -> int:
        return len(self.examples)

    def _apply_template(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        tokenize: bool,
        return_tensors: Optional[str] = None,
    ):
        """
        调用分词器的聊天模板（apply_chat_template）。

        apply_chat_template 的作用：
          把 [{"role": "user", "content": "..."}, ...] 这样的消息列表，
          转换成模型实际看到的文本（带特殊标记），例如：
            <|im_start|>user\n你好<|im_end|>\n<|im_start|>assistant\n

        参数：
          tokenize=True  -- 直接返回 token id 序列
          tokenize=False -- 返回可读文本字符串
          add_generation_prompt=False -- 不在末尾加 assistant 开头标记
                                         （训练时用，推理时需要设为 True）
        """
        kwargs = dict(tokenize=tokenize, add_generation_prompt=False)
        if return_tensors is not None:
            kwargs["return_tensors"] = return_tensors
        if tools and self._use_tools_kw:
            kwargs["tools"] = tools
        return self.tokenizer.apply_chat_template(messages, **kwargs)

    def _extract_ids(self, result) -> List[int]:
        """
        兼容新旧版本 transformers 的返回类型差异。

        旧版（transformers < 4.51）：
          apply_chat_template(tokenize=True) 返回 list[int]

        新版（transformers >= 4.51）：
          返回 BatchEncoding（类似字典），需要取 ["input_ids"] 字段。

        直接用 torch.tensor(result) 时，如果 result 是字典，
        迭代到的是 key（字符串），就会报 "str cannot be interpreted as integer"。
        这个方法统一处理两种情况。
        """
        if isinstance(result, list):
            # 旧版：直接是 list[int]
            return result
        if isinstance(result, dict) or hasattr(result, "input_ids"):
            # 新版：BatchEncoding，取 input_ids 字段
            ids = result["input_ids"]
            # BatchEncoding 的 input_ids 可能是 list 或 tensor，统一转 list
            if isinstance(ids, torch.Tensor):
                return ids.squeeze().tolist()
            return list(ids)
        # 兜底：尝试直接转换
        return list(result)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        单样本构造流程：

        Step 1：对完整 messages 做一次模板化，得到 full_ids（总 token 序列）。

        Step 2：前缀差分法定位每条 assistant 消息的 token 区间：
          - 对 messages[:1] 模板化，长度记为 len_1
          - 对 messages[:2] 模板化，长度记为 len_2
          - ...
          - 若第 i 条消息 role == "assistant"，
            则其 token 区间为 [prev_len, cur_len)
          这样不依赖任何特殊标记的位置假设，纯粹通过长度差分定位。

        Step 3：根据 only_last_assistant 决定对哪些区间计算 loss。

        Step 4：超长截断（从头部截断，保留尾部的最新对话轮次）。

        Step 5：构造张量并返回。
        """
        ex = self.examples[idx]
        messages: List[Dict[str, Any]] = ex["messages"]
        tools: Optional[List[Dict[str, Any]]] = ex.get("tools")

        # Step 1：完整序列模板化
        try:
            full_ids = self._extract_ids(
                self._apply_template(messages, tools, tokenize=True, return_tensors=None)
            )
        except Exception:
            # 降级：不传 tools，使用最基础的调用方式
            full_ids = self._extract_ids(
                self.tokenizer.apply_chat_template(
                    messages, tokenize=True, add_generation_prompt=False
                )
            )
        total_len = len(full_ids)

        # Step 2：前缀差分，找出每条 assistant 消息的 token 区间
        assistant_spans: List[Tuple[int, int]] = []
        prev_len = 0
        for i, msg in enumerate(messages):
            try:
                prefix_ids = self._extract_ids(
                    self._apply_template(
                        messages[: i + 1], tools, tokenize=True, return_tensors=None
                    )
                )
            except Exception:
                prefix_ids = self._extract_ids(
                    self.tokenizer.apply_chat_template(
                        messages[: i + 1], tokenize=True, add_generation_prompt=False
                    )
                )
            cur_len = len(prefix_ids)

            if msg.get("role") == "assistant":
                start, end = prev_len, cur_len
                if end > start:
                    assistant_spans.append((start, end))

            prev_len = cur_len

        # Step 3：构造 loss mask（bool 张量，True = 参与 loss）
        assistant_mask = torch.zeros(total_len, dtype=torch.bool)
        if self.only_last_assistant:
            # 只对最后一条 assistant 回复计算 loss
            # 适用于：数据集中每条样本有多轮对话，
            # 但只想让模型学会"最终回复"的风格
            if len(assistant_spans) > 0:
                start, end = assistant_spans[-1]
                assistant_mask[start:end] = True
        else:
            # 对所有 assistant 回复计算 loss
            for start, end in assistant_spans:
                assistant_mask[start:end] = True

        # Step 4：超长截断（从头部截断，保留尾部）
        # 为什么保留尾部而非头部？
        # 多轮对话中，最后几轮是模型需要学习的目标，
        # 截掉头部的早期对话，对最终 loss 影响较小。
        if total_len > self.max_seq_length:
            overflow = total_len - self.max_seq_length
            full_ids = full_ids[overflow:]
            assistant_mask = assistant_mask[overflow:]

        # Step 5：构造张量
        # input_ids：模型的输入 token 序列
        input_ids = torch.tensor(full_ids, dtype=torch.long)

        # attention_mask：全 1，表示所有位置都参与注意力计算（无 padding）
        attention_mask = torch.ones_like(input_ids)

        # labels：loss 计算目标
        # - 与 input_ids 相同的位置（assistant 区域）：保留原始 token id
        # - 其他位置（user/system）：置为 -100（PyTorch 自动忽略）
        labels = input_ids.clone()
        labels[~assistant_mask] = -100

        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


# ──────────────────────────────────────────────────────────────────
# Batch Collator
# ──────────────────────────────────────────────────────────────────

class DataCollatorForCausal:
    """
    将变长样本对齐成 batch。

    为什么需要这个？
      每条样本的 seq_len 不同（对话长度各异），
      GPU 要求 batch 内所有样本维度相同，
      所以需要在右侧补 padding 对齐到 batch 内最长序列。

    各字段的 padding 值：
      input_ids:      pad_token_id（通常是 eos_token_id）
      attention_mask: 0（告诉模型不要关注 padding 位置）
      labels:         -100（padding 位置不计算 loss）

    pad_to_multiple_of：
      将序列长度对齐到某个倍数（如 8 或 16）。
      在部分 GPU 上能提高矩阵运算效率（tensor core 对齐）。
    """

    def __init__(
        self,
        tokenizer: AutoTokenizer,
        pad_to_multiple_of: Optional[int] = None,
    ) -> None:
        self.tokenizer = tokenizer
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(
        self, features: List[Dict[str, torch.Tensor]]
    ) -> Dict[str, torch.Tensor]:
        input_ids = [f["input_ids"] for f in features]
        attention_masks = [f["attention_mask"] for f in features]
        labels = [f["labels"] for f in features]

        # pad_sequence：把长度不同的 tensor 列表 padding 到相同长度
        batch_input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids, batch_first=True, padding_value=self.tokenizer.pad_token_id
        )
        batch_attention_mask = torch.nn.utils.rnn.pad_sequence(
            attention_masks, batch_first=True, padding_value=0
        )
        batch_labels = torch.nn.utils.rnn.pad_sequence(
            labels, batch_first=True, padding_value=-100
        )

        # 可选：对齐到 pad_to_multiple_of 的倍数
        if self.pad_to_multiple_of is not None:

            def _pad_to_multiple(t: torch.Tensor, value: int) -> torch.Tensor:
                length = t.size(1)
                pad_len = (
                    self.pad_to_multiple_of - length % self.pad_to_multiple_of
                ) % self.pad_to_multiple_of
                if pad_len == 0:
                    return t
                pad_shape = (t.size(0), pad_len)
                pad_tensor = torch.full(pad_shape, value, dtype=t.dtype, device=t.device)
                return torch.cat([t, pad_tensor], dim=1)

            batch_input_ids = _pad_to_multiple(batch_input_ids, self.tokenizer.pad_token_id)
            batch_attention_mask = _pad_to_multiple(batch_attention_mask, 0)
            batch_labels = _pad_to_multiple(batch_labels, -100)

        return {
            "input_ids": batch_input_ids,
            "attention_mask": batch_attention_mask,
            "labels": batch_labels,
        }


# ──────────────────────────────────────────────────────────────────
# 命令行可视化工具
# ──────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Qwen SFT dataset: visualize assistant-only mask and converted tensors"
    )
    parser.add_argument(
        "--data_file", type=str,
        default=str(processed_data_dir() / "merged_train_final.json"),
        help="Path to JSON/JSONL file"
    )
    parser.add_argument(
        "--model_name_or_path", type=str,
        default=str(default_model_dir()),
        help="Tokenizer source"
    )
    parser.add_argument("--max_seq_length", type=int, default=20000)
    parser.add_argument("--num_samples", type=int, default=1, help="Number of samples to print")
    parser.add_argument("--start", type=int, default=0, help="Start index in dataset")
    parser.add_argument("--show_tokens", action="store_true", help="Show token strings rather than ids")
    parser.add_argument("--max_print_tokens", type=int, default=20000, help="Max tokens to print per sample")
    parser.add_argument("--color", action="store_true", help="Use ANSI colors to highlight loss tokens")
    parser.add_argument("--export_dir", type=str, default="", help="Optional dir to export converted tensors per sample as JSON")
    parser.add_argument("--local_files_only", action="store_true", help="Load tokenizer only from local files (offline)")
    parser.add_argument("--show_ignored_segments", action="store_true", help="Show decoded spans that do NOT contribute to loss")
    parser.add_argument("--show_full_decoded", action="store_true", help="Show full decoded text per sample")
    parser.add_argument("--only_last_assistant", action="store_true", help="Only mask the last assistant segment for loss")
    parser.add_argument(
        "--tools_file", type=str,
        default=str(tools_schema_path()),
        help="Path to JSON file with a list of tools to inject when sample.tools is missing"
    )
    parser.add_argument("--tools_json", type=str, default="", help="Inline JSON string (list) of tools to inject")
    return parser.parse_args()


def _ansi(color: str) -> str:
    """ANSI 颜色转义码，用于终端高亮输出。"""
    codes = {
        "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
        "blue": "\033[34m", "magenta": "\033[35m", "cyan": "\033[36m",
        "bold": "\033[1m", "reset": "\033[0m",
    }
    return codes.get(color, "")


def _highlight(tokens: List[str], loss_mask: torch.Tensor, use_color: bool) -> str:
    """将 token 序列按 loss_mask 高亮显示。"""
    assert len(tokens) == loss_mask.numel()
    parts: List[str] = []
    for i, tok in enumerate(tokens):
        if loss_mask[i].item():
            if use_color:
                parts.append(f"{_ansi('green')}{tok}{_ansi('reset')}")
            else:
                parts.append(f"[{tok}]")
        else:
            parts.append(tok)
    return " ".join(parts)


def _contiguous_true_spans(mask: torch.Tensor) -> List[Tuple[int, int]]:
    """将布尔 mask 拆分为连续为 True 的区间列表 [start, end)。"""
    spans: List[Tuple[int, int]] = []
    start = None
    for i, v in enumerate(mask.tolist()):
        if v and start is None:
            start = i
        elif not v and start is not None:
            spans.append((start, i))
            start = None
    if start is not None:
        spans.append((start, mask.numel()))
    return spans


def _export_sample_json(
    path: str,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    labels: torch.Tensor,
) -> None:
    """将单条样本的张量导出为 JSON，便于离线排查。"""
    data = {
        "input_ids": input_ids.tolist(),
        "attention_mask": attention_mask.tolist(),
        "labels": labels.tolist(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def main() -> None:
    args = parse_args()

    print(f"Loading tokenizer: {args.model_name_or_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name_or_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # 加载全局工具列表（可选）
    default_tools = None
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

    print(f"Loading dataset: {args.data_file}")
    dataset = JsonlConversations(
        args.data_file,
        tokenizer,
        args.max_seq_length,
        args.only_last_assistant,
        default_tools=default_tools,
    )

    total = len(dataset)
    start = max(0, args.start)
    end = min(total, start + args.num_samples)

    if args.export_dir:
        os.makedirs(args.export_dir, exist_ok=True)

    for idx in range(start, end):
        sample = dataset[idx]
        input_ids = sample["input_ids"]
        attention_mask = sample["attention_mask"]
        labels = sample["labels"]

        # labels != -100 的位置就是参与 loss 的位置
        loss_mask = labels.ne(-100)

        head_len = min(input_ids.numel(), args.max_print_tokens)
        head_input_ids = input_ids[:head_len]
        head_loss_mask = loss_mask[:head_len]

        print("\n" + "=" * 80)
        print(f"Sample #{idx} / {total}")
        print(
            f"seq_len={input_ids.numel()} | "
            f"loss_tokens={int(loss_mask.sum().item())} | "
            f"masked_out={int((~loss_mask).sum().item())}"
        )

        if args.show_tokens:
            tokens = tokenizer.convert_ids_to_tokens(head_input_ids.tolist())
            line = _highlight(tokens, head_loss_mask, args.color)
            print("Tokens (green or [brackets] = contribute to loss):")
            print(line)
        else:
            ids_line = " ".join(str(i) for i in head_input_ids.tolist())
            mask_line = " ".join("1" if b else "." for b in head_loss_mask.tolist())
            print("input_ids:")
            print(ids_line)
            print("loss_mask (1=loss, .=ignore):")
            print(mask_line)

        spans = _contiguous_true_spans(loss_mask)
        if spans:
            print("Loss segments (decoded with special tokens):")
            for s, e in spans:
                segment_ids = input_ids[s:e]
                text = tokenizer.decode(segment_ids, skip_special_tokens=False)
                display_text = text if len(text) <= 512 else (text[:509] + "...")
                print(f"  [{s}:{e}] -> {display_text!r}")
        else:
            print("No loss segments found (unexpected for assistant-only masking)")

        if args.show_ignored_segments:
            ignored_spans = _contiguous_true_spans(~loss_mask)
            if ignored_spans:
                print("Ignored segments (decoded with special tokens):")
                for s, e in ignored_spans:
                    segment_ids = input_ids[s:e]
                    text = tokenizer.decode(segment_ids, skip_special_tokens=False)
                    display_text = text if len(text) <= 512 else (text[:509] + "...")
                    print(f"  [{s}:{e}] -> {display_text!r}")
            else:
                print("No ignored segments (all tokens contribute to loss)")

        if args.show_full_decoded:
            print("Full decoded (skip_special_tokens=True):")
            print(tokenizer.decode(input_ids.tolist(), skip_special_tokens=True))
            print("Full decoded (skip_special_tokens=False):")
            print(tokenizer.decode(input_ids.tolist(), skip_special_tokens=False))

        if args.export_dir:
            out_path = os.path.join(args.export_dir, f"sample_{idx:06d}.json")
            _export_sample_json(out_path, input_ids, attention_mask, labels)
            print(f"Exported tensors to: {out_path}")


if __name__ == "__main__":
    main()


# 使用示例：
# python -u src/train/inspect_qwen_dataset.py \
#   --data_file data/processed/merged_train_final.json \
#   --model_name_or_path models/Qwen3-1.7B-Base \
#   --tools_file src/tools/all_tools.json \
#   --only_last_assistant \
#   --num_samples 8 --start 0 --show_full_decoded