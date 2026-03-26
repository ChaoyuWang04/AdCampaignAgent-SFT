# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import maybe_generate_with_openai


def validate_creative_spec(
    file_path: str,
    platform: str,
    ad_format: str = "interstitial",
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        return {
            "valid": True,
            "file_path": file_path,
            "platform": platform,
            "ad_format": ad_format,
            "file_size": "24.6MB",
            "resolution": "1080x1920",
            "duration": "15s",
            "format": "MP4",
            "checks_passed": 5,
        }

    system_prompt = "你是广告素材规格审核助手。请严格返回JSON对象。"
    user_prompt = (
        f"请检查素材 file_path={file_path} 在平台={platform}、广告格式={ad_format} 下是否合规。"
        "返回字段 valid，如果不合规返回 errors 列表；如果合规则返回 file_size/resolution/duration/format/checks_passed。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
