#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RLVR 总 reward 聚合器。

职责：
- 收集每个 reward component
- 应用 reward gating
- 按固定权重聚合为最终标量 reward

和 GRPO / RLVR 的关系：
- GRPO 最终使用的是 `total`
- 但训练调试仍需要保留完整的 reward breakdown
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from src.rlvr.reward_components import (
    argument_reward,
    behavior_reward,
    efficiency_penalty,
    format_reward,
    safety_reward,
    success_reward,
    tool_selection_reward,
    workflow_reward,
)
from src.rlvr.rollout import RolloutTrace

try:
    from src.benchmark.benchmark_schema import BenchmarkCase
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))
    from benchmark_schema import BenchmarkCase


WEIGHTS = {
    "format": 0.10,
    "behavior": 0.15,
    "tool_selection": 0.20,
    "argument": 0.20,
    "workflow": 0.10,
    "safety": 0.10,
    "success": 0.25,
    "efficiency": -0.10,
}
POSITIVE_WEIGHT_SUM = sum(weight for weight in WEIGHTS.values() if weight > 0)


@dataclass(slots=True)
class RewardBreakdown:
    """训练时用于观测和调试的 reward 分解结果。"""
    format: float
    behavior: float
    tool_selection: float
    argument: float
    workflow: float
    safety: float
    success: float
    efficiency: float
    total: float


def compute_reward(trace: RolloutTrace, case: BenchmarkCase) -> RewardBreakdown:
    """
    将一条 rollout trace 聚合为最终 reward。

    聚合步骤：
    1. 先独立计算每个 reward component
    2. 再应用 gating 规则
    3. 最后按固定权重加权求和

    gating 规则：
    - 如果 `format_reward == 0.0`：
      - 说明 trace 在格式层已经不可用
      - 除 `format` 外，其余分项全部清零
    - 如果 `behavior_reward < 0.5`：
      - 说明高层动作决策已经错误
      - `tool_selection / argument / workflow` 只保留 30%

    最终 total 不是限制在 [0, 1] 内的概率值，而是加权后的训练 reward。
    由于存在：
    - `safety_reward = -1.0`
    - `efficiency_penalty > 0` 且对应负权重
    所以 total 可以小于 0。
    """
    reward_format = format_reward(trace, case)
    reward_behavior = behavior_reward(trace, case)
    reward_tool_selection = tool_selection_reward(trace, case)
    reward_argument = argument_reward(trace, case)
    reward_workflow = workflow_reward(trace, case)
    reward_safety = safety_reward(trace, case)
    reward_success = success_reward(trace, case)
    reward_efficiency = efficiency_penalty(trace, case)

    if reward_format == 0.0:
        # 如果连格式都不合法，后续 routing / argument / success 都不再可信，
        # 因此直接整体清零，避免模型靠坏格式碰运气拿分。
        # 结果是：
        # - format 仍然保留 0.0
        # - 除 safety 外，其余分项强制变成 0.0
        # safety 不参与 format gating，因为 oos/clarify 样本可能故意输出坏格式的业务工具调用；
        # 如果这里把 safety 清零，会绕过 `safety_reward = -1.0` 的强惩罚，形成 reward hacking。
        reward_behavior = 0.0
        reward_tool_selection = 0.0
        reward_argument = 0.0
        reward_workflow = 0.0
        reward_success = 0.0
        reward_efficiency = 0.0
    elif reward_behavior == 0.0:
        # 如果高层行为决策已错，局部正确的工具名或参数也只能给弱奖励。
        # 结果是：
        # - tool_selection / argument / workflow 各自乘 0.3
        # - safety / success / format 保持原值
        reward_tool_selection *= 0.3
        reward_argument *= 0.3
        reward_workflow *= 0.3

    raw_total = (
        # `total` 是最终送入 GRPO 的标量 reward。
        WEIGHTS["format"] * reward_format
        + WEIGHTS["behavior"] * reward_behavior
        + WEIGHTS["tool_selection"] * reward_tool_selection
        + WEIGHTS["argument"] * reward_argument
        + WEIGHTS["workflow"] * reward_workflow
        + WEIGHTS["safety"] * reward_safety
        + WEIGHTS["success"] * reward_success
        + WEIGHTS["efficiency"] * reward_efficiency
    )
    total = raw_total / POSITIVE_WEIGHT_SUM

    return RewardBreakdown(
        format=reward_format,
        behavior=reward_behavior,
        tool_selection=reward_tool_selection,
        argument=reward_argument,
        workflow=reward_workflow,
        safety=reward_safety,
        success=reward_success,
        efficiency=reward_efficiency,
        total=total,
    )
