from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_COMPLETION_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class YandexGPTError(RuntimeError):
    pass


class YandexGPTClient:
    """Minimal client for Yandex Foundation Models (YandexGPT)."""

    def __init__(
        self,
        api_key: str | None = None,
        folder_id: str | None = None,
        model: str = "yandexgpt/latest",
        timeout: float = 120.0,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("YANDEX_API_KEY")
            or os.getenv("YANDEXGPT_API_KEY")
            or ""
        ).strip()
        self.folder_id = (
            folder_id
            or os.getenv("YANDEX_FOLDER_ID")
            or os.getenv("YANDEXGPT_FOLDER_ID")
            or ""
        ).strip()
        self.model = (
            os.getenv("YANDEX_MODEL")
            or model
        ).strip()
        self.timeout = timeout
        self.completion_url = os.getenv(
            "YANDEX_COMPLETION_URL", DEFAULT_COMPLETION_URL
        ).strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.folder_id)

    def _auth_header(self) -> str:
        if self.api_key.startswith("t1.") or self.api_key.startswith("AQVN"):
            return f"Api-Key {self.api_key}"
        return f"Bearer {self.api_key}"

    def _model_uri(self) -> str:
        if self.model.startswith("gpt://"):
            return self.model
        return f"gpt://{self.folder_id}/{self.model}"

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 6000,
    ) -> str:
        if not self.configured:
            raise YandexGPTError(
                "Yandex GPT is not configured. Set YANDEX_API_KEY and YANDEX_FOLDER_ID."
            )

        payload: dict[str, Any] = {
            "modelUri": self._model_uri(),
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": str(max_tokens),
            },
            "messages": messages,
        }
        headers = {
            "Authorization": self._auth_header(),
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.completion_url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise YandexGPTError(
                    f"Yandex GPT HTTP {response.status_code}: {response.text[:500]}"
                )
            data = response.json()

        try:
            return data["result"]["alternatives"][0]["message"]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise YandexGPTError(f"Unexpected Yandex GPT response: {data}") from exc

    def ping(self, prompt: str = "Ответь одним словом: ок") -> str:
        return self.complete(
            [
                {"role": "system", "text": "Ты помощник."},
                {"role": "user", "text": prompt},
            ],
            temperature=0.0,
            max_tokens=32,
        )
