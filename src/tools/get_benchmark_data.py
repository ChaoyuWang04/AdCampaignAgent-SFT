# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import normalize_rag_chunks, rag_search


def get_benchmark_data(
    metric: str,
    game_genre: str,
    region: str = "US",
    platform: str = "Meta",
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        benchmark_map = {
            "roas": {"d7": {"p25": 0.72, "p50": 0.88, "p75": 1.05}, "d30": {"p25": 1.05, "p50": 1.22, "p75": 1.48}},
            "retention_d1": {"p25": 0.28, "p50": 0.35, "p75": 0.42},
            "retention_d7": {"p25": 0.09, "p50": 0.12, "p75": 0.15},
            "ctr": {"p25": 0.018, "p50": 0.03, "p75": 0.046},
            "cpi": {"p25": 0.95, "p50": 1.55, "p75": 2.45},
        }
        return {
            "metric": metric,
            "genre": game_genre,
            "region": region,
            "platform": platform,
            "benchmark": benchmark_map.get(metric, benchmark_map["roas"]),
        }

    payload = rag_search(
        query=f"{platform} {region} {game_genre} {metric} benchmark",
        fallback_factory=fallback,
        search_type="hybrid",
        limit=3,
    )
    if "results" in payload:
        chunks = normalize_rag_chunks(payload)
        return {
            "metric": metric,
            "genre": game_genre,
            "region": region,
            "platform": platform,
            "rag_chunks": chunks,
            "benchmark": fallback()["benchmark"],
        }
    return payload
