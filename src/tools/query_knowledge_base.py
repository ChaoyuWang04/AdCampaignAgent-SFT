# -*- coding: utf-8 -*-

from typing import Any, Dict

from src.tools._shared import normalize_rag_chunks, rag_search


def query_knowledge_base(
    question: str,
    domain: str = "knowledge_base",
    search_mode: str = "hybrid",
    top_k: int = 5,
) -> Dict[str, Any]:
    def fallback() -> Dict[str, Any]:
        chunks = {
            "bidding_strategy": [
                {
                    "source": "UA Playbook",
                    "content": "tROAS 适合有稳定事件回传和充足转化量的Campaign；切换时建议逐步放量，避免学习期重置。",
                }
            ],
            "creative_guideline": [
                {
                    "source": "Creative Guide",
                    "content": "视频前三秒应突出失败、反转或强冲突场景，优先展示核心玩法反馈。",
                }
            ],
            "platform_policy": [
                {
                    "source": "Policy Notes",
                    "content": "游戏广告不得使用误导性玩法展示，涉及年龄分级或内购内容时需要明确披露。",
                }
            ],
            "industry_benchmark": [
                {
                    "source": "Benchmark Notes",
                    "content": "休闲游戏在美国市场常见的D7 ROAS安全线通常在0.75到0.95之间，具体需结合平台和地区判断。",
                }
            ],
        }
        selected = chunks.get(domain, chunks["bidding_strategy"])
        return {"question": question, "domain": domain, "chunks": selected, "total": len(selected)}

    payload = rag_search(
        query=f"[{domain}] {question}",
        fallback_factory=fallback,
        search_type=search_mode,
        limit=top_k,
    )
    if "results" in payload:
        chunks = normalize_rag_chunks(payload)
        return {"question": question, "domain": domain, "chunks": chunks, "total": len(chunks)}
    return payload
