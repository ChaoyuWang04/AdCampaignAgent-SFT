# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Optional

from src.tools._shared import maybe_generate_with_openai


def get_appsflyer_report(
    app_id: str,
    report_type: str = "retention",
    date_range: Optional[Dict[str, str]] = None,
    groupby: Optional[List[str]] = None,
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        return {
            "app_id": app_id,
            "report_type": report_type,
            "date_range": date_range or {"start": "2026-03-01", "end": "2026-03-07"},
            "groupby": groupby or ["media_source", "country"],
            "data": {
                "retention_d1": 0.33,
                "retention_d7": 0.11,
                "installs": 8520,
                "revenue_d7": 11850.0,
                "revenue_d30": 23140.0,
                "top_media_source": "Meta",
            },
        }

    system_prompt = "你是AppsFlyer归因报表助手。请严格返回JSON对象。"
    user_prompt = (
        f"请返回 app_id={app_id} 的AppsFlyer报表。report_type={report_type}，"
        f"date_range={date_range or {'start': '2026-03-01', 'end': '2026-03-07'}}，groupby={groupby or ['media_source', 'country']}。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
