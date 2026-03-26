#!/usr/bin/env python3
# coding: utf-8

import argparse
import inspect
import json
import os
import sys
import uuid
from typing import Any, Callable, Dict, List

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import src.tools as ad_tools
from src.common.project_paths import default_model_dir, tools_schema_path
from src.inference.local_toolcall_inspector import (
    SYSTEM_PROMPT,
    build_messages,
    extract_assistant,
    extract_tool_calls,
    load_tools,
)


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
    parser.add_argument("--max_tool_rounds", type=int, default=4, help="Max chained tool rounds per user turn")
    return parser.parse_args()


def supports_tools_kw(tokenizer) -> bool:
    try:
        sig = inspect.signature(tokenizer.apply_chat_template)
        return any(p.name == "tools" for p in sig.parameters.values())
    except Exception:
        return False


class LocalToolcallREPL:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.tools = load_tools(args)
        self.dispatch: Dict[str, Callable[..., Any]] = {
            name: getattr(ad_tools, name)
            for name in ad_tools.__all__
        }
        self.history: List[Dict[str, Any]] = []

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

        self.system_message = build_messages("占位消息")[0]

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
        if not isinstance(input_ids, torch.Tensor):
            input_ids = torch.tensor(input_ids)
        if input_ids.ndim == 1:
            input_ids = input_ids.unsqueeze(0)
        return input_ids.to(self.model.device)

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
            print(SYSTEM_PROMPT)
            continue

        repl.run_turn(user_input)


if __name__ == "__main__":
    main()
