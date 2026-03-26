# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import maybe_generate_with_openai


def upload_creative_asset(
    file_path: str,
    campaign_id: str,
    asset_type: str = "video",
    ad_group_id: str = "",
    creative_name: str = "",
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        return {
            "asset_id": "ASSET_2031",
            "status": "uploaded",
            "file_path": file_path,
            "asset_type": asset_type,
            "campaign_id": campaign_id,
            "ad_group_id": ad_group_id or "AG_201",
            "creative_name": creative_name or "new_creative",
            "review_status": "pending",
            "estimated_review": "2-4 hours",
        }

    system_prompt = "你是广告素材上传助手。请严格返回JSON对象。"
    user_prompt = (
        f"请返回一次素材上传结果。file_path={file_path}，campaign_id={campaign_id}，"
        f"asset_type={asset_type}，ad_group_id={ad_group_id or 'AG_201'}，creative_name={creative_name or 'new_creative'}。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
