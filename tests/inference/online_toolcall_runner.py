#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ad Campaign Agent online tool-call runner.
Uses an OpenAI-compatible API endpoint to test external model function-calling
and executes local tool implementations for inspection.
"""

import json
import os
import sys
from typing import Any, Callable, Dict, List

from openai import OpenAI

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.common.project_paths import tools_schema_path
import src.tools as ad_tools


SYSTEM_PROMPT = """你是一个专业的移动游戏广告投放 AI 助手（Ad Campaign Agent），服务于 UA 团队。
当请求需要素材、数据、平台规则、benchmark 或优化建议时，优先调用工具。
上传素材前必须先调用 validate_creative_spec。
对越权操作或无关请求必须拒绝。
不要输出思维过程。"""


class OnlineToolcallRunner:
    def __init__(self, model_name: str = "qwen-plus"):
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.tools = json.loads(tools_schema_path().read_text(encoding="utf-8"))
        self.dispatch: Dict[str, Callable[..., Any]] = {
            name: getattr(ad_tools, name)
            for name in ad_tools.__all__
        }

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        result = self.dispatch[name](**arguments)
        return json.dumps(result, ensure_ascii=False)

    def run_once(self, user_message: str) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=self.tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in (message.tool_calls or [])
                ],
            }
        )

        for tool_call in message.tool_calls or []:
            arguments = json.loads(tool_call.function.arguments)
            tool_result = self.execute_tool(tool_call.function.name, arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

        return messages


if __name__ == "__main__":
    runner = OnlineToolcallRunner(model_name=os.getenv("OPENAI_MODEL", "qwen-plus"))
    trace = runner.run_once("帮我看看 CMP_2048 最近的 campaign 表现。")
    for item in trace:
        print(json.dumps(item, ensure_ascii=False, indent=2))
