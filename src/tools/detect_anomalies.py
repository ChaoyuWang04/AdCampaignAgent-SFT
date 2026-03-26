# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import maybe_generate_with_openai


def detect_anomalies(
    campaign_id: str,
    metric: str = "roas",
    sensitivity: float = 0.75,
    model_name: str | None = None,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        anomalies = [
            {
                "metric": metric,
                "severity": "warning",
                "value": 0.82 if metric == "roas" else 0.021,
                "baseline": 0.95 if metric == "roas" else 0.03,
                "deviation": "-13.7%",
                "possible_causes": [
                    "CPI 上升",
                    "低质量流量占比增加",
                    "素材疲劳导致CVR下降",
                ],
            }
        ]
        return {
            "campaign_id": campaign_id,
            "metric": metric,
            "sensitivity": sensitivity,
            "anomalies": anomalies,
        }

    system_prompt = "你是广告投放异常检测助手。请严格返回JSON对象。"
    user_prompt = (
        f"请检测 campaign_id={campaign_id} 的指标异常，metric={metric}，sensitivity={sensitivity}。"
        "返回字段 campaign_id/metric/sensitivity/anomalies。"
    )
    return maybe_generate_with_openai(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        fallback_factory=fallback,
        expected_type=dict,
        model_name=model_name,
    )
