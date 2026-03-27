#!/usr/bin/env python3
# coding: utf-8

import argparse
import inspect
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import src.tools as ad_tools
from src.common.project_paths import default_model_dir, tools_schema_path


DEFAULT_SYSTEM_PROMPT = """你是一个专业的移动游戏广告投放 AI 助手（Ad Campaign Agent），服务于 UA（User Acquisition）团队。

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


DEFAULT_CONTEXT = """## 广告投放上下文
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

DEFAULT_SYSTEM_PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "ad_agent_system_prompt.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local REPL for Ad Campaign Agent tool-calling")
    parser.add_argument("--model_path", type=str, default=str(default_model_dir()), help="Path to local model dir")
    parser.add_argument("--max_new_tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=1.0)
    parser.add_argument("--top_k", type=int, default=1)
    parser.add_argument("--repetition_penalty", type=float, default=1.1)
    parser.add_argument("--no_repeat_ngram_size", type=int, default=6)
    parser.add_argument("--do_sample", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--device_map_auto", action="store_true")
    parser.add_argument("--local_files_only", action="store_true")
    parser.add_argument("--tools_file", type=str, default=str(tools_schema_path()))
    parser.add_argument("--tools_json", type=str, default="")
    parser.add_argument("--system-file", type=str, default="", help="Path to a custom system prompt file")
    parser.add_argument("--system-text", type=str, default="", help="Inline custom system prompt text")
    parser.add_argument("--max_tool_rounds", type=int, default=4, help="Max chained tool rounds per user turn")
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
    for match in __import__("re").findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, flags=__import__("re").S):
        try:
            calls.append(json.loads(match))
        except json.JSONDecodeError:
            pass
    if calls:
        return calls
    for match in __import__("re").findall(
        r'(\{\s*"name"\s*:\s*".+?"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\})',
        text,
        flags=__import__("re").S,
    ):
        try:
            obj = json.loads(match)
            if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                calls.append(obj)
        except json.JSONDecodeError:
            continue
    return calls


def load_system_prompt(args: argparse.Namespace) -> str:
    if args.system_text:
        return args.system_text
    if args.system_file:
        with open(args.system_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    if DEFAULT_SYSTEM_PROMPT_FILE.exists():
        return DEFAULT_SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    return DEFAULT_SYSTEM_PROMPT


class LocalToolcallREPL:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.tools = load_tools(args)
        self.dispatch: Dict[str, Callable[..., Any]] = {
            name: getattr(ad_tools, name)
            for name in ad_tools.__all__
        }
        self.history: List[Dict[str, Any]] = []
        self.system_prompt = load_system_prompt(args)

        torch_dtype = None
        if args.bf16:
            torch_dtype = torch.bfloat16
        elif args.fp16:
            torch_dtype = torch.float16

        self.tokenizer = AutoTokenizer.from_pretrained(
            args.model_path,
            trust_remote_code=True,
            local_files_only=args.local_files_only,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            args.model_path,
            trust_remote_code=True,
            local_files_only=args.local_files_only,
            torch_dtype=torch_dtype,
            device_map="auto" if args.device_map_auto else None,
        )
        if hasattr(self.model, "config"):
            self.model.config.use_cache = True

        self.system_message = {
            "role": "system",
            "content": DEFAULT_CONTEXT + "\n\n" + self.system_prompt,
        }

    def reset_history(self) -> None:
        self.history = []

    def _render_messages(self, messages: List[Dict[str, Any]]) -> torch.Tensor:
        template_kwargs: Dict[str, Any] = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_tensors": "pt",
        }
        if self.tools is not None and supports_tools_kw(self.tokenizer):
            template_kwargs["tools"] = self.tools

        input_ids = self.tokenizer.apply_chat_template(messages, **template_kwargs)
        if isinstance(input_ids, torch.Tensor):
            tensor_input_ids = input_ids
        elif hasattr(input_ids, "input_ids"):
            tensor_input_ids = torch.tensor(input_ids.input_ids)
        elif hasattr(input_ids, "ids"):
            tensor_input_ids = torch.tensor(input_ids.ids)
        else:
            tensor_input_ids = torch.tensor(input_ids)
        if tensor_input_ids.ndim == 1:
            tensor_input_ids = tensor_input_ids.unsqueeze(0)
        return tensor_input_ids.to(self.model.device)

    def _generate_once(self, messages: List[Dict[str, Any]]) -> str:
        input_ids = self._render_messages(messages)
        attention_mask = torch.ones_like(input_ids)
        generation_kwargs = {
            "max_new_tokens": self.args.max_new_tokens,
            "temperature": self.args.temperature,
            "top_p": self.args.top_p,
            "top_k": self.args.top_k,
            "repetition_penalty": self.args.repetition_penalty,
            "no_repeat_ngram_size": self.args.no_repeat_ngram_size,
            "do_sample": self.args.do_sample,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                **generation_kwargs,
            )
        decoded = self.tokenizer.decode(output_ids[0], skip_special_tokens=False)
        return extract_assistant(decoded)

    def _normalize_tool_calls(self, assistant_text: str) -> List[Dict[str, Any]]:
        parsed_calls = extract_tool_calls(assistant_text)
        normalized: List[Dict[str, Any]] = []
        for call in parsed_calls:
            name = call.get("name")
            arguments = call.get("arguments", {})
            if not name or not isinstance(arguments, dict):
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
        return normalized

    def _execute_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])
        result = self.dispatch[name](**arguments)
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(result, ensure_ascii=False),
        }

    def run_turn(self, user_message: str) -> None:
        self.history.append({"role": "user", "content": user_message})
        tool_round = 0

        while True:
            messages = [self.system_message, *self.history]
            assistant_text = self._generate_once(messages)
            tool_calls = self._normalize_tool_calls(assistant_text)

            print("\nassistant:")
            print(assistant_text)

            if not tool_calls:
                self.history.append({"role": "assistant", "content": assistant_text})
                return

            tool_round += 1
            self.history.append(
                {
                    "role": "assistant",
                    "content": assistant_text,
                    "tool_calls": tool_calls,
                }
            )

            print("\nparsed tool calls:")
            for index, tool_call in enumerate(tool_calls, start=1):
                print(f"[{index}] {tool_call['function']['name']}")
                print(tool_call["function"]["arguments"])

            for tool_call in tool_calls:
                tool_message = self._execute_tool(tool_call)
                self.history.append(tool_message)
                print("\ntool result:")
                print(tool_message["content"])

            if tool_round >= self.args.max_tool_rounds:
                print("\n[stopped after max tool rounds]")
                return

    def print_history_summary(self) -> None:
        if not self.history:
            print("[history is empty]")
            return
        for idx, message in enumerate(self.history, start=1):
            role = message["role"]
            if role == "assistant" and "tool_calls" in message:
                names = [call["function"]["name"] for call in message["tool_calls"]]
                print(f"{idx}. assistant tool_calls={names}")
            elif role == "tool":
                print(f"{idx}. tool tool_call_id={message.get('tool_call_id')}")
            else:
                content = message.get("content", "")
                print(f"{idx}. {role}: {content[:120]}")


def print_help() -> None:
    print("Commands:")
    print("  /exit    Quit REPL")
    print("  /reset   Clear conversation history")
    print("  /history Show current message history")
    print("  /tools   Show available tools")
    print("  /system  Show current system prompt")


def main() -> None:
    args = parse_args()
    repl = LocalToolcallREPL(args)

    print("Local Toolcall REPL")
    print("Type /exit to quit. Type /help for commands.")

    while True:
        try:
            user_input = input("\nuser> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return

        if not user_input:
            continue
        if user_input == "/exit":
            print("bye")
            return
        if user_input == "/help":
            print_help()
            continue
        if user_input == "/reset":
            repl.reset_history()
            print("[history cleared]")
            continue
        if user_input == "/history":
            repl.print_history_summary()
            continue
        if user_input == "/tools":
            print(json.dumps(sorted(repl.dispatch.keys()), ensure_ascii=False, indent=2))
            continue
        if user_input == "/system":
            print(repl.system_prompt)
            continue

        repl.run_turn(user_input)


if __name__ == "__main__":
    main()
