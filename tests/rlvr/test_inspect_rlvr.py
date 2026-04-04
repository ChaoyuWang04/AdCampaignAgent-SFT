#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
import sys

import torch

sys.path.append(str(Path(__file__).resolve().parents[2]))
sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))

from benchmark_schema import BenchmarkCase
from src.rlvr.rollout import AssistantTurnTrace, RolloutTrace


def test_inspect_uses_real_padded_masks_from_trainer():
    from src.rlvr.inspect_rlvr_training_data import build_real_masks
    from src.rlvr.trainer import MultiTurnGRPOTrainer, build_trl_reward_func
    from tests.rlvr.test_trainer_smoke import MockTokenizer, TinyMockModel

    case = BenchmarkCase(
        id="inspect_mask_case",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天的投放表现。",
        context={"platform": "Meta", "campaign_id": "CMP_2048"},
        expected_behavior="tool_call",
    )
    trainer = MultiTurnGRPOTrainer.for_testing(
        model=TinyMockModel(),
        tokenizer=MockTokenizer(),
        reward_func=build_trl_reward_func({case.id: case}),
        case_lookup={case.id: case},
        rollout_runner=lambda **kwargs: RolloutTrace([], [], kwargs["messages"], "no_tool_call"),
    )
    prompt_ids = [11, 12, 13]
    completion_ids = [21, 22]

    prompt_mask, completion_mask = build_real_masks(
        trainer=trainer,
        prompt_ids=prompt_ids,
        completion_ids=completion_ids,
    )

    assert torch.equal(prompt_mask, torch.tensor([[1, 1, 1]], dtype=torch.long))
    assert torch.equal(completion_mask, torch.tensor([[1, 1]], dtype=torch.long))


def test_build_real_masks_preserves_padding_shape():
    from src.rlvr.inspect_rlvr_training_data import build_real_masks
    from src.rlvr.trainer import MultiTurnGRPOTrainer, build_trl_reward_func
    from tests.rlvr.test_trainer_smoke import MockTokenizer, TinyMockModel

    case = BenchmarkCase(
        id="inspect_mask_padding_case",
        case_type="standard",
        user_input="帮我看一下 CMP_2048 最近 7 天的投放表现。",
        context={"platform": "Meta", "campaign_id": "CMP_2048"},
        expected_behavior="tool_call",
    )
    trainer = MultiTurnGRPOTrainer.for_testing(
        model=TinyMockModel(),
        tokenizer=MockTokenizer(),
        reward_func=build_trl_reward_func({case.id: case}),
        case_lookup={case.id: case},
        rollout_runner=lambda **kwargs: RolloutTrace(
            assistant_turns=[
                AssistantTurnTrace("t", [21, 22], [-0.1, -0.2], [], []),
            ],
            tool_messages=[],
            message_history=kwargs["messages"] + [{"role": "assistant", "content": "t"}],
            termination_reason="no_tool_call",
        ),
    )

    prompt_mask, completion_mask = build_real_masks(
        trainer=trainer,
        prompt_ids=[11, 12, 13, 14],
        completion_ids=[21, 22],
    )

    assert prompt_mask.shape == (1, 4)
    assert completion_mask.shape == (1, 2)
