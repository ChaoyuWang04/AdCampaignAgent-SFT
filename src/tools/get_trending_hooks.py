# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import maybe_generate_with_openai


def get_trending_hooks(
    game_genre: str,
    creative_type: str = "video",
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        hooks = [
            {"hook": "90%的人第一关都过不了", "type": "challenge", "avg_ctr": 0.062},
            {"hook": "你能撑过第3关吗？", "type": "challenge", "avg_ctr": 0.058},
            {"hook": "[真实玩家录屏] 我卡了3天的关", "type": "ugc_style", "avg_ctr": 0.055},
        ]
        return {"genre": game_genre, "creative_type": creative_type, "hooks": hooks}

    system_prompt = "你是移动游戏广告创意钩子助手。请严格返回JSON对象。"
    user_prompt = (
        f"请为品类={game_genre}、素材类型={creative_type}生成热门hooks。"
        "返回字段 genre/creative_type/hooks。hooks中的每一项包含 hook/type/avg_ctr。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
