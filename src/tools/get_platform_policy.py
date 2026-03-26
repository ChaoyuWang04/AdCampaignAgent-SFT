# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import normalize_rag_chunks, rag_search


def get_platform_policy(
    platform: str,
    policy_type: str,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        policies = {
            "ad_format": f"{platform} 支持 video / playable / image 等常见游戏广告格式，9:16 通常是推荐比例。",
            "content_restriction": f"{platform} 禁止误导性素材、夸大玩法、过度暴力或未披露的内购诱导内容。",
            "targeting": f"{platform} 支持兴趣、相似受众和自定义受众定向，但未成年用户定向受平台政策限制。",
            "billing": f"{platform} 常见计费方式包括 CPM、CPC、CPA，具体取决于投放目标与优化事件。",
        }
        return {
            "platform": platform,
            "policy_type": policy_type,
            "content": policies.get(policy_type, policies["content_restriction"]),
        }

    payload = rag_search(
        query=f"{platform} {policy_type} advertising policy",
        fallback_factory=fallback,
        search_type="hybrid",
        limit=3,
    )
    if "results" in payload:
        chunks = normalize_rag_chunks(payload)
        content = "\n\n".join(chunk["content"] for chunk in chunks if chunk["content"])
        return {
            "platform": platform,
            "policy_type": policy_type,
            "content": content or fallback()["content"],
            "rag_chunks": chunks,
        }
    return payload
