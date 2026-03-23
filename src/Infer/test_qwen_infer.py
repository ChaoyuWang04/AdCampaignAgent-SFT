#!/usr/bin/env python3
# coding: utf-8

import argparse
import os
import json
import inspect
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

ADCAMPAIGN_SYSTEM_PROMPT = """You are AdCampaignAgent, a professional mobile-game UA assistant for campaign analysis and tool calling.

Responsibilities:
- Analyze campaign health with ROAS, retention, spend, CPI, CTR, and creative signals
- Use tools to inspect campaign metrics, creative performance, AppsFlyer reports, benchmarks, and platform policy
- Ask for missing critical information when campaign scope is unclear
- Refuse destructive or unauthorized account-level operations

Execution rules:
- If the user asks for performance diagnosis, call the relevant analytics tools before answering
- If the user asks for creative ideas, search trending creatives or hooks before summarizing
- If the user asks to upload creatives, validate specs before upload
- Keep final answers grounded in the returned tool data and explicitly compare metrics to baseline when available"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test inference for merged Qwen model (chat)")
    parser.add_argument("--model_path", type=str, default="/root/autodl-tmp/qwen3-0_6b_lora_v5_merged", help="Path to merged model dir")
    # parser.add_argument("--message", type=str, required=True, help="User message to send")
    parser.add_argument("--max_new_tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=1)
    parser.add_argument("--top_k", type=int, default=1)
    parser.add_argument("--repetition_penalty", type=float, default=1.15)
    parser.add_argument("--no_repeat_ngram_size", type=int, default=6)
    parser.add_argument("--bad_words", type=str, default="", help="Optional pipe-separated phrases to ban, e.g. 'phrase A|phrase B'")
    parser.add_argument("--show_tokens", action="store_true", help="Print generated tokens (not IDs) before decode")
    parser.add_argument("--do_sample", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--device_map_auto", action="store_true")
    parser.add_argument("--local_files_only", action="store_true")
    # Tools injection for inference prompt
    parser.add_argument("--tools_file", type=str, default="", help="Path to JSON file with a list of tools (OpenAI/Qwen schema)")
    parser.add_argument("--tools_json", type=str, default="", help="Inline JSON string (list) of tools to pass into chat template")
    parser.add_argument("--show_template", action="store_true", help="Only print apply_chat_template text and token ids, then exit")
    return parser.parse_args()


def extract_assistant(decoded: str) -> str:
    # Try to extract between assistant markers if present
    start_tag = "<|im_start|>assistant"
    end_tag = "<|im_end|>"
    if start_tag in decoded:
        last_start = decoded.rfind(start_tag)
        content = decoded[last_start + len(start_tag):]
        # Strip a leading newline if present
        if content.startswith("\n"):
            content = content[1:]
        # Cut off at end tag if present
        if end_tag in content:
            content = content.split(end_tag, 1)[0]
        return content.strip()
    # Fallback: return full decoded
    return decoded.strip()


def main(args, messages, is_print=True) -> None:

    torch_dtype = None
    if args.bf16:
        torch_dtype = torch.bfloat16
    elif args.fp16:
        torch_dtype = torch.float16

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
        torch_dtype=torch_dtype,
        device_map="auto" if args.device_map_auto else None,
    )

    # Ensure use_cache is enabled for inference
    if hasattr(model, "config"):
        model.config.use_cache = True

    # Optionally load tools
    tools = None
    if args.tools_file:
        with open(args.tools_file, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, list):
            tools = obj
        else:
            raise ValueError("tools_file must contain a JSON array of tool objects")
    elif args.tools_json:
        obj = json.loads(args.tools_json)
        if isinstance(obj, list):
            tools = obj
        else:
            raise ValueError("tools_json must be a JSON array of tool objects")

    # Detect whether tokenizer supports tools kw
    def _supports_tools_kw(tok) -> bool:
        try:
            sig = inspect.signature(tok.apply_chat_template)
            return any(p.name == "tools" for p in sig.parameters.values())
        except Exception:
            return False

    kwargs = dict(tokenize=True, add_generation_prompt=True, return_tensors="pt")
    if tools is not None and _supports_tools_kw(tokenizer):
        kwargs["tools"] = tools

    if args.show_template:
        text_kwargs = dict(tokenize=False, add_generation_prompt=True)
        if tools is not None and _supports_tools_kw(tokenizer):
            text_kwargs["tools"] = tools
        templated_text = tokenizer.apply_chat_template(
            messages,
            **text_kwargs,
        )
        if is_print:
            print("===== apply_chat_template (text) =====")
            print(templated_text)

        # 打印 token ids（前128个）和总长度
        ids_kwargs = dict(tokenize=True, add_generation_prompt=True, return_tensors=None)
        if tools is not None and _supports_tools_kw(tokenizer):
            ids_kwargs["tools"] = tools
        token_ids = tokenizer.apply_chat_template(
            messages,
            **ids_kwargs,
        )
        try:
            if isinstance(token_ids, list):
                flat = token_ids
            else:
                flat = token_ids.squeeze().tolist()
            if is_print:
                print("===== token ids (head) =====")
                print(flat[:128])
                print(f"total token length: {len(flat)}")
        except Exception as e:
            print("[warn] failed to present token ids:", type(token_ids), e)
        return

    # 仅在需要生成时才加载模型
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
        torch_dtype=torch_dtype,
        device_map="auto" if args.device_map_auto else None,
    )

    # Ensure use_cache is enabled for inference
    if hasattr(model, "config"):
        model.config.use_cache = True

    # Build inputs using chat template
    input_ids = tokenizer.apply_chat_template(
        messages,
        **kwargs,
    )
    input_ids = input_ids.to(model.device)

    # Compose EOS ids to include <|im_end|> if distinct from eos_token
    eos_ids = []
    if tokenizer.eos_token_id is not None:
        eos_ids.append(tokenizer.eos_token_id)
    try:
        im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
        if isinstance(im_end_id, int) and im_end_id != -1 and im_end_id != tokenizer.eos_token_id:
            eos_ids.append(im_end_id)
    except Exception:
        pass

    # Optional bad words ids
    bad_words_ids = None
    if args.bad_words.strip():
        phrases = [p.strip() for p in args.bad_words.split("|") if p.strip()]
        if phrases:
            enc = tokenizer(phrases, add_special_tokens=False).input_ids
            bad_words_ids = [ids for ids in enc if len(ids) > 0]

    gen_kwargs = {
        "max_new_tokens": args.max_new_tokens,
        "eos_token_id": eos_ids if len(eos_ids) > 0 else tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
        "do_sample": args.do_sample,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "repetition_penalty": args.repetition_penalty,
        "no_repeat_ngram_size": args.no_repeat_ngram_size,
    }
    if bad_words_ids:
        gen_kwargs["bad_words_ids"] = bad_words_ids

    with torch.inference_mode():
        output_ids = model.generate(input_ids=input_ids, **gen_kwargs)

    # Slice out only the generated continuation (exclude the prompt length)
    gen_only = output_ids[0, input_ids.shape[1]:]

    if args.show_tokens and is_print:
        print("-" * 100)
        print("看解码前token信息")
        # Convert token IDs to token strings without joining so you can see BPE units
        pieces = tokenizer.convert_ids_to_tokens(gen_only.tolist())
        print("TOKENS:")
        print(pieces)
        
    # Only decode the generated continuation
    decoded = tokenizer.decode(output_ids[0], skip_special_tokens=False)
    reply = extract_assistant(decoded)

    if is_print:
        print("-" * 100)
        print("正式回复：")
        print(reply)
    else:
        return reply


if __name__ == "__main__":

    args = parse_args()

    messages = [
      {
        "role": "system",
        "content": ADCAMPAIGN_SYSTEM_PROMPT
      },
      {
        "role": "user",
        "content": "Please analyze campaign CMP_2048 for the last 7 days and tell me whether ROAS and retention are healthy."
      },
    ]

    main(args, messages) 
    
    
# python src/Infer/test_qwen_infer.py --model_path /path/to/merged-model --local_files_only --show_template
    
   
# python -u src/Infer/test_qwen_infer.py \
#   --model_path /path/to/qwen3-0_6b_lora_v2_last_assistant \
#   --bf16 --device_map_auto --local_files_only
