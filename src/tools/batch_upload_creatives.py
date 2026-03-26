# -*- coding: utf-8 -*-

from typing import Any, Dict, List

from src.tools._shared import maybe_generate_with_openai


def batch_upload_creatives(
    file_paths: List[str],
    campaign_id: str,
    naming_convention: str = "{genre}_{region}_{date}_{index}",
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        results = []
        for index, file_path in enumerate(file_paths, start=1):
            results.append(
                {
                    "file": file_path,
                    "status": "uploaded",
                    "asset_id": f"ASSET_{2000 + index}",
                }
            )
        return {
            "campaign_id": campaign_id,
            "naming_convention": naming_convention,
            "total": len(file_paths),
            "success": len(file_paths),
            "failed": 0,
            "results": results,
        }

    system_prompt = "你是广告素材批量上传助手。请严格返回JSON对象。"
    user_prompt = (
        f"请返回一次批量上传结果。campaign_id={campaign_id}，file_paths={file_paths}，"
        f"naming_convention={naming_convention}。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
