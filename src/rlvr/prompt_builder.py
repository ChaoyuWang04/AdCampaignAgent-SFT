#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BenchmarkCase -> multi-turn messages 的转换层。

职责：
- 读取系统提示词
- 将 case.context 渲染到 system message
- 把 `BenchmarkCase` 变成 rollout 可直接消费的 `message list`

和 GRPO / RLVR 的关系：
- 这里输出的是 message list，而不是单次 completion 文本
- 因为后续 rollout 会不断往 history 里追加 tool result 和 assistant turn
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import sys

from src.common.project_paths import repo_root

try:
    from src.benchmark.benchmark_schema import BenchmarkCase
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))
    from benchmark_schema import BenchmarkCase


SYSTEM_PROMPT_PATH = repo_root() / "prompts" / "ad_agent_system_prompt.txt"


def _load_system_prompt() -> str:
    """读取当前 agent 的系统提示词，保证 RLVR 与现有推理路径一致。"""
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def _format_context(context: dict[str, Any]) -> str:
    """把 case.context 格式化为稳定文本，供 system message 使用。"""
    lines = ["## 广告投放上下文"]
    for key, value in context.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def build_case_messages(
    case: BenchmarkCase,
    *,
    history: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    将单条 benchmark case 构造成多轮友好的起始 messages。

    输入：
    - case: 任务定义
    - history: 可选历史消息扩展位

    输出：
    - `system + user (+ history)` 的 message list
    """
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": f"{_format_context(case.context)}\n\n{_load_system_prompt()}",
        },
        {
            "role": "user",
            "content": case.user_input,
        },
    ]
    if history:
        messages.extend(history)
    return messages
