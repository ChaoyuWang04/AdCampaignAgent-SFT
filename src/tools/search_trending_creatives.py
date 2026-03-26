# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import maybe_generate_with_openai


def search_trending_creatives(
    platform: str,
    game_genre: str,
    region: str = "US",
    time_range: int = 7,
    top_k: int = 10,
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        results = [
            {
                "creative_id": "CR_12031",
                "platform": platform,
                "genre": game_genre,
                "region": region,
                "format": "video_15s",
                "hook_type": "challenge",
                "estimated_ctr": 0.061,
                "heat_score": 94.2,
            },
            {
                "creative_id": "CR_12032",
                "platform": platform,
                "genre": game_genre,
                "region": region,
                "format": "playable",
                "hook_type": "ugc_style",
                "estimated_ctr": 0.054,
                "heat_score": 90.8,
            },
        ]
        return {"results": results[: min(top_k, len(results))], "total": min(top_k, len(results))}

    system_prompt = (
        "你是移动游戏UA团队的素材搜索助手。请严格返回JSON对象，不要输出解释。"
        "字段必须包含 results 和 total。"
    )
    user_prompt = (
        f"请为平台={platform}、品类={game_genre}、地区={region}、时间范围={time_range}天"
        "生成热门素材检索结果。每条结果包含 creative_id/platform/genre/region/format/"
        "hook_type/estimated_ctr/heat_score。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
