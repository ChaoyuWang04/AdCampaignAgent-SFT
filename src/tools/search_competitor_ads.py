# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import maybe_generate_with_openai


def search_competitor_ads(
    competitor_name: str,
    platform: str,
    limit: int = 20,
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        ads = [
            {
                "ad_id": "AD_56001",
                "competitor": competitor_name,
                "platform": platform,
                "format": "video_30s",
                "creative_theme": "puzzle_difficulty",
                "estimated_spend": "$32K/week",
                "first_seen": "2026-03-08",
            },
            {
                "ad_id": "AD_56002",
                "competitor": competitor_name,
                "platform": platform,
                "format": "image",
                "creative_theme": "emotional_story",
                "estimated_spend": "$18K/week",
                "first_seen": "2026-03-11",
            },
        ]
        return {"competitor": competitor_name, "ads": ads[: min(limit, len(ads))]}

    system_prompt = "你是竞品广告检索助手。请严格返回JSON对象，不要输出多余文本。"
    user_prompt = (
        f"请为竞品={competitor_name}、平台={platform}生成广告检索结果。"
        "每条广告包含 ad_id/competitor/platform/format/creative_theme/estimated_spend/first_seen。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
