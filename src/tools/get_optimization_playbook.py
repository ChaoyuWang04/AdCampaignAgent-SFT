# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import maybe_generate_with_openai


def get_optimization_playbook(
    issue_type: str,
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        playbooks = {
            "low_roas": [
                "收紧低质量版位和受众包",
                "暂停高花费低回收素材",
                "按素材主题拆分新的测试组",
            ],
            "low_ctr": [
                "更换前三秒钩子",
                "补充UGC风格新素材",
                "复查素材与落地页承接一致性",
            ],
            "creative_fatigue": [
                "本周上线3-5个新素材",
                "降低疲劳素材预算权重",
                "复用高点击hook做变体测试",
            ],
            "budget_underdelivery": [
                "放宽出价或扩大受众范围",
                "检查广告审核与投放状态",
                "提高预算分配到高潜力单元",
            ],
        }
        return {
            "issue_type": issue_type,
            "priority": "high",
            "actions": playbooks.get(issue_type, playbooks["low_roas"]),
        }

    system_prompt = "你是UA优化策略助手。请严格返回JSON对象。"
    user_prompt = (
        f"请为问题类型={issue_type} 生成优化playbook。"
        "返回字段 issue_type/priority/actions。actions是字符串数组。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
