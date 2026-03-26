#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Manual smoke test for the external-model tool-call runner.
"""

import os
import sys

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from online_toolcall_runner import OnlineToolcallRunner


def test_runner_smoke() -> None:
    print("=== Online Toolcall Runner Smoke Test ===")
    runner = OnlineToolcallRunner(model_name=os.getenv("OPENAI_MODEL", "qwen-plus"))
    messages = runner.run_once("帮我查一下 Playrix 最近在 Meta 上投了什么广告。")
    print(f"trace length: {len(messages)}")
    for message in messages:
        print(message["role"], "tool_calls" if "tool_calls" in message else "")


if __name__ == "__main__":
    test_runner_smoke()
