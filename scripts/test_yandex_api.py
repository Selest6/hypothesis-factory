#!/usr/bin/env python3
"""Quick smoke test for Yandex AI Studio GPT (embeddings are local, no API)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

import httpx

from src.rag.embeddings import YandexEmbeddings


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")


def test_embedding() -> None:
    embedder = YandexEmbeddings()
    vector = embedder.embed_query("тест Yandex embeddings")
    print(f"Yandex embedding OK: dim={len(vector)}")


def test_completion() -> None:
    api_key = os.getenv("YANDEX_API_KEY") or os.getenv("YC_API_KEY")
    folder_id = os.getenv("YANDEX_FOLDER_ID") or os.getenv("YC_FOLDER_ID")
    model = os.getenv("YANDEX_COMPLETION_MODEL", "yandexgpt/latest")

    if not api_key or not folder_id:
        raise ValueError("Missing YANDEX_API_KEY / YANDEX_FOLDER_ID")

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    payload = {
        "modelUri": f"gpt://{folder_id}/{model}",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": 64,
        },
        "messages": [
            {
                "role": "user",
                "text": "Ответь одним словом: работает?",
            }
        ],
    }
    response = httpx.post(
        url,
        headers={"Authorization": f"Api-Key {api_key}"},
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    text = data["result"]["alternatives"][0]["message"]["text"]
    print(f"Completion OK ({model}): {text.strip()}")


def main() -> None:
    _load_env()
    print("Testing Yandex embeddings + GPT...\n")
    test_embedding()
    test_completion()
    print("\nAll checks passed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
