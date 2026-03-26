# -*- coding: utf-8 -*-

from typing import Any, Dict, Optional

from src.tools._shared import maybe_generate_with_openai


def get_creative_performance(
    campaign_id: str,
    sort_by: str = "ctr",
    top_k: int = 10,
    date_range: Optional[Dict[str, str]] = None,
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        creatives = [
            {
                "creative_id": "CR_70101",
                "name": "casual_video_01_US",
                "format": "video_15s",
                "ctr": 0.041,
                "cpi": 1.42,
                "roas_d7": 0.96,
                "spend": 4200.0,
                "installs": 2957,
                "status": "active",
            },
            {
                "creative_id": "CR_70102",
                "name": "casual_playable_02_US",
                "format": "playable",
                "ctr": 0.036,
                "cpi": 1.58,
                "roas_d7": 0.88,
                "spend": 3150.0,
                "installs": 1993,
                "status": "active",
            },
        ]
        return {
            "campaign_id": campaign_id,
            "sort_by": sort_by,
            "date_range": date_range or {"start": "2026-03-01", "end": "2026-03-07"},
            "creatives": creatives[: min(top_k, len(creatives))],
        }

    system_prompt = "你是广告素材效果分析助手。请严格返回JSON对象。"
    user_prompt = (
        f"请返回 campaign_id={campaign_id} 的素材表现结果，sort_by={sort_by}，"
        f"top_k={top_k}，date_range={date_range or {'start': '2026-03-01', 'end': '2026-03-07'}}。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
