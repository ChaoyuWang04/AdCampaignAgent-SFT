#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))

from benchmark_schema import BenchmarkCase


class MockModel:
    def __init__(self, responses):
        self._responses = list(responses)

    def rlvr_generate(self, *, messages, tokenizer):
        _ = messages
        _ = tokenizer
        if not self._responses:
            raise AssertionError("No more mock responses configured")
        return self._responses.pop(0)


class MockTokenizer:
    def encode(self, text, add_special_tokens=False):
        _ = add_special_tokens
        return [ord(char) for char in text]


def test_run_rollout_returns_trace_with_assistant_turns_and_tool_results():
    from src.rlvr.prompt_builder import build_case_messages
    from src.rlvr.rollout import run_rollout

    case = BenchmarkCase(
        id="std_rollout",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天的投放表现。",
        context={"platform": "Meta", "campaign_id": "CMP_2048", "region": "US"},
        expected_behavior="tool_call",
    )
    messages = build_case_messages(case)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_campaign_metrics",
                "description": "Get campaign metrics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "string"},
                    },
                    "required": ["campaign_id"],
                },
            },
        }
    ]
    model = MockModel(
        [
            {
                "assistant_text": '<tool_call>{"name":"get_campaign_metrics","arguments":{"campaign_id":"CMP_2048"}}</tool_call>',
                "token_ids": [101, 102, 103],
                "logprobs": [-0.1, -0.2, -0.3],
            },
            {
                "assistant_text": "最近 7 天 ROAS 与留存基本达标，CTR 正常。",
                "token_ids": [201, 202],
                "logprobs": [-0.4, -0.5],
            },
        ]
    )
    tokenizer = MockTokenizer()

    trace = run_rollout(
        model=model,
        tokenizer=tokenizer,
        messages=messages,
        tools=tools,
        max_tool_rounds=5,
    )

    assert trace.termination_reason == "no_tool_call"
    assert len(trace.assistant_turns) == 2
    assert trace.assistant_turns[0].token_ids == [101, 102, 103]
    assert trace.assistant_turns[0].logprobs == [-0.1, -0.2, -0.3]
    assert trace.assistant_turns[0].tool_calls[0]["function"]["name"] == "get_campaign_metrics"
    assert len(trace.tool_messages) == 1
    assert trace.tool_messages[0]["role"] == "tool"
    assert trace.message_history[0]["role"] == "system"
    assert trace.message_history[1]["role"] == "user"
    assert trace.message_history[-1]["role"] == "assistant"


def test_run_rollout_stops_at_max_rounds():
    from src.rlvr.prompt_builder import build_case_messages
    from src.rlvr.rollout import run_rollout

    case = BenchmarkCase(
        id="seq_rollout",
        case_type="sequential",
        user_input="继续查一下另一个 campaign。",
        context={"platform": "Meta", "campaign_id": "CMP_3001"},
        expected_behavior="tool_call",
    )
    messages = build_case_messages(case)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_campaign_metrics",
                "description": "Get campaign metrics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "string"},
                    },
                    "required": ["campaign_id"],
                },
            },
        }
    ]
    model = MockModel(
        [
            {
                "assistant_text": '<tool_call>{"name":"get_campaign_metrics","arguments":{"campaign_id":"CMP_3001"}}</tool_call>',
                "token_ids": [1],
                "logprobs": [-0.1],
            },
            {
                "assistant_text": '<tool_call>{"name":"get_campaign_metrics","arguments":{"campaign_id":"CMP_3001"}}</tool_call>',
                "token_ids": [2],
                "logprobs": [-0.2],
            },
        ]
    )

    trace = run_rollout(
        model=model,
        tokenizer=MockTokenizer(),
        messages=messages,
        tools=tools,
        max_tool_rounds=2,
    )

    assert trace.termination_reason == "max_rounds"
    assert len(trace.assistant_turns) == 2
    assert len(trace.tool_messages) == 2
    assert trace.message_history[-1]["role"] == "assistant"
    assert trace.message_history[-1]["content"] == ""


def test_run_rollout_without_tool_call_finishes_immediately():
    from src.rlvr.prompt_builder import build_case_messages
    from src.rlvr.rollout import run_rollout

    case = BenchmarkCase(
        id="reject_rollout",
        case_type="oos",
        user_input="帮我把所有 campaign 的预算都清零。",
        context={"platform": "Meta"},
        expected_behavior="reject",
    )
    messages = build_case_messages(case)
    model = MockModel(
        [
            {
                "assistant_text": "抱歉，我无法执行清零所有 campaign 预算这样的越权操作。",
                "token_ids": [9, 8],
                "logprobs": [-0.2, -0.3],
            }
        ]
    )

    trace = run_rollout(
        model=model,
        tokenizer=MockTokenizer(),
        messages=messages,
        tools=[],
        max_tool_rounds=5,
    )

    assert trace.termination_reason == "no_tool_call"
    assert len(trace.assistant_turns) == 1
    assert trace.tool_messages == []
    assert trace.assistant_turns[0].assistant_text.startswith("抱歉")


def test_run_rollout_never_returns_dead_done_termination_reason():
    from src.rlvr.prompt_builder import build_case_messages
    from src.rlvr.rollout import run_rollout

    case = BenchmarkCase(
        id="reject_rollout_done_guard",
        case_type="oos",
        user_input="帮我把所有 campaign 的预算都清零。",
        context={"platform": "Meta"},
        expected_behavior="reject",
    )
    trace = run_rollout(
        model=MockModel(
            [
                {
                    "assistant_text": "抱歉，我无法执行清零所有 campaign 预算这样的越权操作。",
                    "token_ids": [9, 8],
                    "logprobs": [-0.2, -0.3],
                }
            ]
        ),
        tokenizer=MockTokenizer(),
        messages=build_case_messages(case),
        tools=[],
        max_tool_rounds=5,
    )

    assert trace.termination_reason != "done"


def test_run_rollout_prefers_case_specific_max_tool_rounds():
    from src.rlvr.prompt_builder import build_case_messages
    from src.rlvr.rollout import run_rollout

    case = BenchmarkCase(
        id="seq_rollout_case_limit",
        case_type="sequential",
        user_input="继续查一下另一个 campaign。",
        context={"platform": "Meta", "campaign_id": "CMP_3001"},
        expected_behavior="tool_call",
        rlvr_max_tool_rounds=1,
    )
    messages = build_case_messages(case)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_campaign_metrics",
                "description": "Get campaign metrics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "string"},
                    },
                    "required": ["campaign_id"],
                },
            },
        }
    ]
    model = MockModel(
        [
            {
                "assistant_text": '<tool_call>{"name":"get_campaign_metrics","arguments":{"campaign_id":"CMP_3001"}}</tool_call>',
                "token_ids": [1],
                "logprobs": [-0.1],
            },
            {
                "assistant_text": '<tool_call>{"name":"get_campaign_metrics","arguments":{"campaign_id":"CMP_3001"}}</tool_call>',
                "token_ids": [2],
                "logprobs": [-0.2],
            },
        ]
    )

    trace = run_rollout(
        model=model,
        tokenizer=MockTokenizer(),
        messages=messages,
        tools=tools,
        max_tool_rounds=3,
        case=case,
    )

    assert trace.termination_reason == "max_rounds"
    assert len(trace.assistant_turns) == 1
    assert trace.message_history[-1]["role"] == "assistant"
    assert trace.message_history[-1]["content"] == ""


def test_run_rollout_preserves_malformed_tool_call_signal():
    from src.rlvr.prompt_builder import build_case_messages
    from src.rlvr.rollout import run_rollout

    case = BenchmarkCase(
        id="std_bad_tool_call",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天的投放表现。",
        context={"campaign_id": "CMP_2048"},
        expected_behavior="tool_call",
    )
    messages = build_case_messages(case)
    model = MockModel(
        [
            {
                "assistant_text": '<tool_call>{"name":"get_campaign_metrics","arguments":"not-a-dict"}</tool_call>',
                "token_ids": [7, 8],
                "logprobs": [-0.1, -0.2],
            }
        ]
    )

    trace = run_rollout(
        model=model,
        tokenizer=MockTokenizer(),
        messages=messages,
        tools=[],
        max_tool_rounds=5,
    )

    assert trace.termination_reason == "malformed_tool_call"
    assert len(trace.assistant_turns) == 1
    assert trace.assistant_turns[0].assistant_text
    assert trace.assistant_turns[0].tool_calls == []


def test_tool_dispatch_is_built_once_at_module_load():
    from src.rlvr.rollout import _TOOL_DISPATCH

    assert isinstance(_TOOL_DISPATCH, dict)
    assert "get_campaign_metrics" in _TOOL_DISPATCH
