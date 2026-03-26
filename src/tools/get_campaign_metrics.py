# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Optional

from src.tools._shared import maybe_generate_with_openai


def get_campaign_metrics(
    campaign_id: str,
    metrics: Optional[List[str]] = None,
    date_range: Optional[Dict[str, str]] = None,
    breakdown: str = "daily",
    model_name: str | None = None,
) -> Dict[str, Any]:
    requested_metrics = metrics or ["roas", "retention_d1", "retention_d7", "ctr", "cpi", "spend", "installs"]

    def fallback() -> Dict[str, Any]:
        metric_values: Dict[str, Any] = {}
        for name in requested_metrics:
            if name == "roas":
                metric_values[name] = {"d7": 0.91, "d30": 1.24}
            elif name == "retention_d1":
                metric_values[name] = 0.34
            elif name == "retention_d7":
                metric_values[name] = 0.12
            elif name == "ctr":
                metric_values[name] = 0.031
            elif name == "cpi":
                metric_values[name] = 1.72
            elif name == "spend":
                metric_values[name] = 12450.0
            elif name == "installs":
                metric_values[name] = 7238
            elif name == "cpm":
                metric_values[name] = 10.4
        return {
            "campaign_id": campaign_id,
            "date_range": date_range or {"start": "2026-03-01", "end": "2026-03-07"},
            "breakdown": breakdown,
            "metrics": metric_values,
        }

    system_prompt = "你是移动游戏投放数据助手。请严格返回JSON对象。"
    user_prompt = (
        f"请返回 campaign_id={campaign_id} 的投放指标。metrics={requested_metrics}，"
        f"date_range={date_range or {'start': '2026-03-01', 'end': '2026-03-07'}}，breakdown={breakdown}。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
