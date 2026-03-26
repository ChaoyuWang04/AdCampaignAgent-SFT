# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Optional

from src.tools._shared import maybe_generate_with_openai


def compare_campaigns(
    campaign_ids: List[str],
    metrics: Optional[List[str]] = None,
    date_range: Optional[Dict[str, str]] = None,
    model_name: str | None = None,
) -> Dict[str, Any]:
    requested_metrics = metrics or ["roas", "retention_d1", "cpi", "spend"]

    def fallback() -> Dict[str, Any]:
        comparison = []
        for index, campaign_id in enumerate(campaign_ids, start=1):
            comparison.append(
                {
                    "campaign_id": campaign_id,
                    "roas_d7": round(0.98 - (index - 1) * 0.11, 3),
                    "ret_d1": round(0.34 - (index - 1) * 0.03, 3),
                    "ret_d7": round(0.12 - (index - 1) * 0.01, 3),
                    "cpi": round(1.45 + (index - 1) * 0.27, 2),
                    "spend": round(12000 - (index - 1) * 2100, 2),
                    "installs": 6800 - (index - 1) * 950,
                }
            )
        return {
            "metrics": requested_metrics,
            "date_range": date_range or {"start": "2026-03-01", "end": "2026-03-07"},
            "comparison": comparison,
        }

    system_prompt = "你是广告投放对比分析助手。请严格返回JSON对象。"
    user_prompt = (
        f"请对比 campaign_ids={campaign_ids}，metrics={requested_metrics}，"
        f"date_range={date_range or {'start': '2026-03-01', 'end': '2026-03-07'}}。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
