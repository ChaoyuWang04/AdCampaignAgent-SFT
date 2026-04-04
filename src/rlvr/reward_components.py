#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 `RolloutTrace` 适配为 benchmark evaluator 可理解的 reward 分项。

职责：
- 不重写 benchmark 评分逻辑
- 只做 trace 格式适配
- 输出每个 reward component 的原始分数

和 GRPO / RLVR 的关系：
- 这些函数提供 dense reward 的基础信号
- `reward.py` 会在此基础上做 gating 和加权聚合
"""

from __future__ import annotations

import json
from typing import Any
from pathlib import Path
import sys

from src.rlvr.rollout import RolloutTrace

try:
    from src.benchmark.benchmark_schema import BenchmarkCase
    from src.benchmark.benchmark_utils import parse_tool_arguments
    from src.benchmark.eval_content import evaluate_content_case
    from src.benchmark.eval_format import evaluate_format_case
    from src.benchmark.eval_routing import evaluate_routing_case
    from src.benchmark.eval_system import evaluate_system_case
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2] / "src" / "benchmark"))
    from benchmark_schema import BenchmarkCase
    from benchmark_utils import parse_tool_arguments
    from eval_content import evaluate_content_case
    from eval_format import evaluate_format_case
    from eval_routing import evaluate_routing_case
    from eval_system import evaluate_system_case


BUSINESS_TOOL_BEHAVIOR_CASE_TYPES = {"oos", "clarify"}


def _to_benchmark_trace(trace: RolloutTrace) -> list[dict[str, Any]]:
    """把 rollout history 映射成 benchmark evaluator 期望的 trace 格式。"""
    return trace.message_history[1:]


def format_reward(trace: RolloutTrace, case: BenchmarkCase) -> float:
    """
    格式层奖励，对应 benchmark 的 F1 / F2。

    评分规则：
    - 先做本地硬校验：
      - tool name 不是非空字符串 -> 直接返回 0.0
      - arguments 如果是字符串但不是合法 JSON -> 直接返回 0.0
      - arguments 解析后不是 dict -> 直接返回 0.0
      - arguments 既不是 str 也不是 dict -> 直接返回 0.0
    - 如果通过本地硬校验，再调用 benchmark 的 `evaluate_format_case`
    - benchmark 返回空字典时：
      - 如果这条 case 本来就不该调工具 -> 返回 1.0
      - 如果这条 case 应该调工具但 trace 里没有可评分 tool call -> 返回 0.0
    - 正常情况下返回 `(F1 + F2) / 2`

    分值含义：
    - 1.0：格式完全合规，且在不该调工具的场景下正确没有工具调用
    - 0.5：通常表示可解析但格式不完全合规，例如 F1=1, F2=0
    - 0.0：没有 tool call、tool call 结构坏掉，或参数无法解析成字典
    - 不会返回负数
    """
    if trace.termination_reason == "malformed_tool_call":
        return 0.0

    for turn in trace.assistant_turns:
        for tool_call in turn.tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name")
            arguments = function.get("arguments", {})
            # 非法工具名：格式层直接失败。
            if not isinstance(name, str) or not name:
                return 0.0
            if isinstance(arguments, str):
                try:
                    parsed = __import__("json").loads(arguments)
                except Exception:
                    # arguments 不是合法 JSON 字符串：格式层直接失败。
                    return 0.0
                if not isinstance(parsed, dict):
                    # arguments 虽可解析，但不是对象/字典：格式层直接失败。
                    return 0.0
            elif not isinstance(arguments, dict):
                # arguments 类型非法：格式层直接失败。
                return 0.0

    scores = evaluate_format_case(case, _to_benchmark_trace(trace))
    if not scores:
        # benchmark 对“不该调工具”的样本会跳过格式评分：
        # - 非 tool-call 样本：没有工具调用是正确行为，因此给 1.0
        # - tool-call 样本：本该调工具却没调，给 0.0
        return 1.0 if case.expected_behavior != "tool_call" else 0.0
    # F1 = 是否存在可解析 tool call，F2 = 结构是否合规；这里取平均。
    return (scores.get("F1", 0.0) + scores.get("F2", 0.0)) / 2


def behavior_reward(trace: RolloutTrace, case: BenchmarkCase) -> float:
    """
    高层行为决策奖励，对应 R1。

    评分规则：
    - predicted behavior == case.expected_behavior -> 1.0
    - 否则 -> 0.0

    这里的 behavior 指的是顶层动作类别：
    - `tool_call`
    - `reject`
    - `clarify`

    分值含义：
    - 1.0：顶层行为判断正确
    - 0.0：顶层行为判断错误
    - 不会返回负数
    """
    scores = evaluate_routing_case(case, _to_benchmark_trace(trace))
    return scores.get("R1", 0.0)


def tool_selection_reward(trace: RolloutTrace, case: BenchmarkCase) -> float:
    """
    工具选择奖励，对应 R2 / R3。

    评分规则：
    - 如果这条 case 不要求 tool_call：
      - 直接返回 1.0
      - 因为这类样本不参与工具选择评分，正确的顶层行为已由 R1 负责
    - 如果这条 case 要求 tool_call：
      - R2 = 工具序列是否完全一致，取值 0.0 或 1.0
      - R3 = 工具集合的 multiset F1，取值区间 [0.0, 1.0]
      - 最终返回 `(R2 + R3) / 2`

    分值含义：
    - 1.0：工具顺序完全正确，且工具集合完全匹配
    - 0.5 左右：通常表示工具集合部分命中，但顺序不完全对
    - 0.0：完全没有命中预期工具，或应调工具却没调
    - 不会返回负数
    """
    scores = evaluate_routing_case(case, _to_benchmark_trace(trace))
    if case.expected_behavior != "tool_call":
        return 1.0
    r2 = scores.get("R2", 0.0)
    r3 = scores.get("R3", 0.0)
    return (r2 + r3) / 2


def argument_reward(trace: RolloutTrace, case: BenchmarkCase) -> float:
    """
    参数质量奖励，对应 C1 / C2。

    评分规则：
    - 如果这条 case 不要求 tool_call：
      - 直接返回 1.0
      - 因为这类样本本来就没有参数比较任务
    - 如果这条 case 要求 tool_call，但 evaluator 没有拿到任何可比较参数：
      - 返回 0.0
    - 如果有可比较参数：
      - C1 = 参数整体是否完全一致，取值 0.0 或 1.0
      - C2 = 参数字段命中率平均值，取值区间 [0.0, 1.0]
      - 最终返回 `(C1 + C2) / 2`

    分值含义：
    - 1.0：参数完全一致
    - 0.5 左右：部分字段正确，但整体不完全一致
    - 0.0：没填对任何关键参数，或应调工具却没有有效参数可比
    - 不会返回负数
    """
    if case.expected_behavior == "tool_call" and not case.expected_tool_args:
        return 1.0

    scores = evaluate_content_case(case, _to_benchmark_trace(trace))
    if not scores:
        return 1.0 if case.expected_behavior != "tool_call" else 0.0
    return (scores.get("C1", 0.0) + scores.get("C2", 0.0)) / 2


def workflow_reward(trace: RolloutTrace, case: BenchmarkCase) -> float:
    """
    顺序 / 并行工作流奖励，对应 S1 / S2。

    评分规则：
    - sequential case:
      - predicted_sequence == expected_sequence -> 1.0
      - 否则 -> 0.0
    - parallel case:
      - 预期并行工具组出现在同一 assistant turn 中 -> 1.0
      - 否则 -> 0.0
    - 其他 case:
      - 直接返回 1.0
      - 因为这些样本不参与 workflow 评分

    分值含义：
    - 1.0：工作流约束满足
    - 0.0：工作流约束不满足
    - 不会返回负数
    """
    scores = evaluate_system_case(case, _to_benchmark_trace(trace))
    if case.case_type == "sequential":
        return scores.get("S1", 0.0)
    if case.case_type == "parallel":
        return scores.get("S2", 0.0)
    return 1.0


def safety_reward(trace: RolloutTrace, case: BenchmarkCase) -> float:
    """
    安全行为奖励，对应拒答 / 澄清相关维度。

    评分规则：
    - 如果 case_type 是 `oos` 或 `clarify`，但 trace 里出现了业务工具调用：
      - 直接返回 -1.0
      - 这是本文件里唯一会显式给到负分的 reward component
    - reject 样本：
      - 正确拒答 -> 1.0
      - 否则 -> 0.0
    - clarify 样本：
      - 正确追问且覆盖缺失槽位 -> 区间 [0.0, 1.0]
      - 完全没追问或追问方向错误 -> 0.0
    - 其他样本：
      - 直接返回 1.0

    分值含义：
    - 1.0：安全行为完全正确
    - 0.0：该拒答/澄清但没有做到
    - -1.0：oos/clarify 场景里误调业务工具，属于强惩罚
    """
    benchmark_trace = _to_benchmark_trace(trace)
    has_tool_calls = any(turn.tool_calls for turn in trace.assistant_turns)
    if case.case_type in BUSINESS_TOOL_BEHAVIOR_CASE_TYPES and has_tool_calls:
        # oos / clarify 类样本只要误调业务工具，就视为严重错误，直接给负分。
        return -1.0

    scores = evaluate_system_case(case, benchmark_trace)
    if case.expected_behavior == "reject":
        return scores.get("S3", 0.0)
    if case.expected_behavior == "clarify":
        return scores.get("S4", 0.0)
    return 1.0


def success_reward(trace: RolloutTrace, case: BenchmarkCase) -> float:
    """
    端到端成功奖励，对应 S5。

    评分规则来自 benchmark 的 `_task_success`：
    - reject 样本：
      - 正确拒答且没有任何工具调用 -> 1.0
      - 否则 -> 0.0
    - clarify 样本：
      - 正确澄清且没有任何工具调用 -> 1.0
      - 否则 -> 0.0
    - sequential 样本：
      - R1 正确、S1 正确、且最终有非空 assistant 终态回答 -> 1.0
      - 否则 -> 0.0
    - parallel 样本：
      - R1 正确、S2 正确、且最终有非空 assistant 终态回答 -> 1.0
      - 否则 -> 0.0
    - 普通 tool_call 样本：
      - behavior == tool_call
      - R2 == 1.0
      - C2 == 1.0
      - 存在最终非空 assistant 回答
      - 同时满足时 -> 1.0
      - 否则 -> 0.0

    分值含义：
    - 1.0：整条任务链规则化成功
    - 0.0：整条任务链未达到成功条件
    - 不会返回负数
    """
    scores = evaluate_system_case(case, _to_benchmark_trace(trace))
    return scores.get("S5", 0.0)


def efficiency_penalty(trace: RolloutTrace, case: BenchmarkCase) -> float:
    """
    效率惩罚项，用来抑制 benchmark 外的低效行为。

    评分规则：
    - 初始为 0.0，表示“没有罚分”
    - 先根据 case 推算“预期工具调用数”
      - standard -> 1
      - sequential -> `len(expected_sequence)`
      - parallel -> `sum(len(group) for group in expected_parallel_groups)`
      - oos / clarify -> 0
      - 其他情况 -> 1
    - 如果 termination_reason == "max_rounds"：
      - 加 0.3 罚分
    - 如果总 tool call 数超出任务预期：
      - 每多一次额外调用，加 0.1 罚分
    - 如果出现重复调用（工具名 + 参数完全相同）：
      - 每次重复额外加 0.2 罚分

    分值含义：
    - 0.0：没有观察到额外低效行为
    - 正数：越大表示越低效
    - 不会返回负数

    注意：
    - 这里返回的是“正的罚分量”
    - 在 `reward.py` 中会乘以负权重 `WEIGHTS["efficiency"] = -0.10`
    - 所以它最终会对 total reward 产生负贡献
    """
    penalty = 0.0
    tool_call_count = sum(len(turn.tool_calls) for turn in trace.assistant_turns)

    if case.case_type == "standard":
        expected = 1
    elif case.case_type == "sequential":
        expected = len(case.expected_sequence)
    elif case.case_type == "parallel":
        expected = sum(len(group) for group in case.expected_parallel_groups)
    elif case.case_type in ("oos", "clarify"):
        expected = 0
    else:
        expected = 1

    if trace.termination_reason == "max_rounds":
        penalty += 0.3

    extra_calls = max(0, tool_call_count - expected)
    penalty += 0.1 * extra_calls

    repeated_signatures: set[tuple[str, str]] = set()
    repeated_calls = 0
    for turn in trace.assistant_turns:
        for tool_call in turn.tool_calls:
            arguments = parse_tool_arguments(tool_call["function"].get("arguments", {}))
            signature = (
                tool_call["function"]["name"],
                json.dumps(arguments, sort_keys=True, ensure_ascii=False),
            )
            if signature in repeated_signatures:
                repeated_calls += 1
            repeated_signatures.add(signature)
    if repeated_calls:
        penalty += 0.2 * repeated_calls

    return penalty
