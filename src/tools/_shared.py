# -*- coding: utf-8 -*-

import json
import os
from typing import Any, Callable, Optional

import requests
from openai import OpenAI


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_RAG_API_URL = "http://127.0.0.1:8010"


def _extract_json_snippet(raw_text: str) -> str:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        raise ValueError("Empty response")

    candidates = [
        ("{", "}"),
        ("[", "]"),
    ]
    for start_token, end_token in candidates:
        start = raw_text.find(start_token)
        end = raw_text.rfind(end_token)
        if start != -1 and end != -1 and end >= start:
            return raw_text[start : end + 1]
    return raw_text


def parse_json_response(raw_text: str, expected_type: Optional[type] = None) -> Any:
    payload = json.loads(_extract_json_snippet(raw_text))
    if expected_type and not isinstance(payload, expected_type):
        raise TypeError(f"Expected {expected_type.__name__}, got {type(payload).__name__}")
    return payload


def maybe_generate_with_openai(
    *,
    system_prompt: str,
    user_prompt: str,
    fallback_factory: Callable[[], Any],
    expected_type: Optional[type] = dict,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Any:
    resolved_api_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
    if not resolved_api_key:
        return fallback_factory()

    resolved_model = model_name or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    resolved_base_url = base_url or os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL)

    try:
        client = OpenAI(api_key=resolved_api_key, base_url=resolved_base_url)
        response = client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        return parse_json_response(content, expected_type=expected_type)
    except Exception:
        return fallback_factory()


def rag_search(
    *,
    query: str,
    fallback_factory: Callable[[], Any],
    search_type: str = "hybrid",
    limit: int = 5,
    rag_api_url: Optional[str] = None,
) -> Any:
    base_url = (rag_api_url or os.getenv("RAG_API_URL", DEFAULT_RAG_API_URL)).rstrip("/")
    try:
        response = requests.post(
            f"{base_url}/search",
            json={
                "query": query,
                "search_type": search_type,
                "vector_weight": 0.7,
                "keyword_weight": 1.5,
                "limit": limit,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            return fallback_factory()
        return payload
    except Exception:
        return fallback_factory()


def normalize_rag_chunks(payload: dict) -> list[dict]:
    chunks = []
    for item in payload.get("results", []):
        chunks.append(
            {
                "source": item.get("title") or item.get("source") or "RAG Search",
                "content": item.get("content") or item.get("text") or "",
            }
        )
    return chunks
