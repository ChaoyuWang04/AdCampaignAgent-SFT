#!/usr/bin/env python3
# coding: utf-8

import argparse
import inspect
import json
import os
import re
import sys
from typing import Any, Dict, List

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common.project_paths import default_model_dir, tools_schema_path


SYSTEM_PROMPT = """你是一个专业的移动游戏广告投放 AI 助手（Ad Campaign Agent），服务于 UA（User Acquisition）团队。

## 核心职责
- 判断用户请求属于素材搜索、素材上传、指标查询、深度分析、异常诊断、知识问答还是拒答场景
- 当问题需要数据、素材、平台政策、benchmark 或诊断时，优先调用工具，不要臆测
- 分析效果时，明确指出 ROAS / Retention 是否达到安全基线
- 对越权操作、无关问题、信息不足的问题做正确处理

## 工具调用原则
- 如果用户在问热门素材、竞品广告、热门钩子，调用素材相关工具
- 如果用户要上传素材，先调用 validate_creative_spec，再决定是否调用 upload_creative_asset 或 batch_upload_creatives
- 如果用户在问 campaign / creative / AppsFlyer 数据，调用对应分析工具
- 如果用户在问异常原因或优化建议，优先调用 detect_anomalies 或 get_optimization_playbook
- 如果用户在问 benchmark、平台政策、投放知识，调用 query_knowledge_base / get_benchmark_data / get_platform_policy
- 如果信息不足以调用工具，先追问一个最关键的信息
- 对删除广告、清空预算、导出其他团队数据、黑客类请求，必须拒绝

## 输出要求
- 如果需要工具，直接输出 tool call
- 如果不需要工具，直接输出简洁自然语言答案
- 不要输出思维过程
"""


SAMPLE_SCENARIOS = {
    "creative_search": "帮我看看 Meta 上最近美国 casual 品类的热门素材。",
    "competitor_ads": "查一下 Playrix 最近在 Meta 上投了什么广告。",
    "campaign_metrics": "帮我看一下 CMP_2048 最近的 campaign 表现。",
    "creative_upload": "把 assets/casual_video_03.mp4 上传到 CMP_2048。",
    "anomaly": "CMP_2048 最近 ROAS 掉得厉害，帮我排查一下。",
    "benchmark": "美国 casual 游戏的 ROAS benchmark 大概是多少？",
    "policy": "Meta 对游戏广告的内容限制有哪些？",
    "refusal": "帮我把所有 campaign 的预算都清零。",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect local model tool-calling behavior for Ad Campaign Agent")
    parser.add_argument("--model_path", type=str, default=str(default_model_dir()), help="Path to local model dir")
    parser.add_argument("--message", type=str, default="", help="User message to send")
    parser.add_argument("--scenario", type=str, default="campaign_metrics", choices=sorted(SAMPLE_SCENARIOS.keys()))
    parser.add_argument("--max_new_tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=1.0)
    parser.add_argument("--top_k", type=int, default=1)
    parser.add_argument("--repetition_penalty", type=float, default=1.1)
    parser.add_argument("--no_repeat_ngram_size", type=int, default=6)
    parser.add_argument("--show_tokens", action="store_true")
    parser.add_argument("--do_sample", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--device_map_auto", action="store_true")
    parser.add_argument("--local_files_only", action="store_true")
    parser.add_argument("--tools_file", type=str, default=str(tools_schema_path()))
    parser.add_argument("--tools_json", type=str, default="")
    parser.add_argument("--show_template", action="store_true")
    return parser.parse_args()


def load_tools(args: argparse.Namespace) -> List[Dict[str, Any]] | None:
    if args.tools_json:
        payload = json.loads(args.tools_json)
    elif args.tools_file:
        with open(args.tools_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        return None
    if not isinstance(payload, list):
        raise ValueError("Tools payload must be a JSON array")
    return payload


def supports_tools_kw(tokenizer) -> bool:
    try:
        sig = inspect.signature(tokenizer.apply_chat_template)
        return any(p.name == "tools" for p in sig.parameters.values())
    except Exception:
        return False


def extract_assistant(decoded: str) -> str:
    start_tag = "<|im_start|>assistant"
    end_tag = "<|im_end|>"
    if start_tag in decoded:
        last_start = decoded.rfind(start_tag)
        content = decoded[last_start + len(start_tag):]
        if content.startswith("\n"):
            content = content[1:]
        if end_tag in content:
            content = content.split(end_tag, 1)[0]
        return content.strip()
    return decoded.strip()


def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    for match in re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, flags=re.S):
        try:
            calls.append(json.loads(match))
        except json.JSONDecodeError:
            pass

    if calls:
        return calls

    # Fallback: look for inline OpenAI-style function-call objects.
    for match in re.findall(r'(\{\s*"name"\s*:\s*".+?"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\})', text, flags=re.S):
        try:
            obj = json.loads(match)
            if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                calls.append(obj)
        except json.JSONDecodeError:
            continue

    return calls


def build_messages(user_message: str) -> List[Dict[str, str]]:
    context = """## 广告投放上下文
- 平台: Meta
- 游戏品类: casual
- 地区: US
- campaign_id: CMP_2048
- app_id: APP_9001
- 用户角色: UA Manager
- D7 ROAS安全线: 0.85
- D30 ROAS安全线: 1.20
- D1 留存安全线: 35%
- D7 留存安全线: 12%
- 数据窗口: 2026-03-01 ~ 2026-03-07
"""
    return [
        {"role": "system", "content": context + "\n\n" + SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def run_inference(args: argparse.Namespace, messages: List[Dict[str, str]]) -> str:
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
    if hasattr(model, "config"):
        model.config.use_cache = True

    tools = load_tools(args)
    template_kwargs: Dict[str, Any] = {
        "tokenize": True,
        "add_generation_prompt": True,
        "return_tensors": "pt",
    }
    if tools is not None and supports_tools_kw(tokenizer):
        template_kwargs["tools"] = tools

    if args.show_template:
        text_kwargs: Dict[str, Any] = {"tokenize": False, "add_generation_prompt": True}
        if tools is not None and supports_tools_kw(tokenizer):
            text_kwargs["tools"] = tools
        templated_text = tokenizer.apply_chat_template(messages, **text_kwargs)
        print("===== apply_chat_template (text) =====")
        print(templated_text)
        return ""

    input_ids = tokenizer.apply_chat_template(messages, **template_kwargs)
    if not isinstance(input_ids, torch.Tensor):
        input_ids = torch.tensor(input_ids)
    if input_ids.ndim == 1:
        input_ids = input_ids.unsqueeze(0)
    input_ids = input_ids.to(model.device)
    attention_mask = torch.ones_like(input_ids)

    generation_kwargs = {
        "max_new_tokens": args.max_new_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "repetition_penalty": args.repetition_penalty,
        "no_repeat_ngram_size": args.no_repeat_ngram_size,
        "do_sample": args.do_sample,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }

    with torch.no_grad():
        output_ids = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            **generation_kwargs,
        )

    gen_ids = output_ids[0, input_ids.shape[-1]:]
    if args.show_tokens:
        print("===== generated tokens =====")
        print(tokenizer.convert_ids_to_tokens(gen_ids.tolist()))
    decoded = tokenizer.decode(output_ids[0], skip_special_tokens=False)
    return extract_assistant(decoded)


def pretty_print_result(user_message: str, assistant_text: str) -> None:
    tool_calls = extract_tool_calls(assistant_text)

    print("===== user =====")
    print(user_message)
    print("\n===== assistant =====")
    print(assistant_text)

    if tool_calls:
        print("\n===== parsed tool calls =====")
        for idx, tool_call in enumerate(tool_calls, start=1):
            print(f"[{idx}] name: {tool_call.get('name')}")
            print(json.dumps(tool_call.get("arguments", {}), ensure_ascii=False, indent=2))
    else:
        print("\n===== parsed tool calls =====")
        print("No tool call detected")


if __name__ == "__main__":
    args = parse_args()
    user_message = args.message or SAMPLE_SCENARIOS[args.scenario]
    messages = build_messages(user_message)
    assistant_text = run_inference(args, messages)
    if assistant_text:
        pretty_print_result(user_message, assistant_text)
