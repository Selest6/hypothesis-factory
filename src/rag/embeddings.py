from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Literal

import httpx

EmbeddingKind = Literal["document", "query"]

DEFAULT_EMBEDDING_URL = (
    "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"
)


@dataclass
class EmbeddingConfig:
    api_key: str
    folder_id: str
    doc_model: str = "text-search-doc/latest"
    query_model: str = "text-search-query/latest"
    base_url: str = DEFAULT_EMBEDDING_URL
    max_retries: int = 8
    retry_delay: float = 3.0
    request_timeout: float = 90.0
    batch_pause: float = 0.15

    @classmethod
    def from_env(cls) -> EmbeddingConfig:
        api_key = os.getenv("YANDEX_API_KEY") or os.getenv("YC_API_KEY")
        folder_id = os.getenv("YANDEX_FOLDER_ID") or os.getenv("YC_FOLDER_ID")
        if not api_key or not folder_id:
            raise ValueError(
                "Set YANDEX_API_KEY and YANDEX_FOLDER_ID in .env "
                "(or YC_API_KEY / YC_FOLDER_ID)."
            )
        return cls(
            api_key=api_key,
            folder_id=folder_id,
            doc_model=os.getenv("YANDEX_EMBEDDING_DOC_MODEL", "text-search-doc/latest"),
            query_model=os.getenv(
                "YANDEX_EMBEDDING_QUERY_MODEL", "text-search-query/latest"
            ),
            base_url=os.getenv("YANDEX_EMBEDDING_URL", DEFAULT_EMBEDDING_URL),
        )


class YandexEmbeddings:
    """Yandex Foundation Models text embeddings via API."""

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self.config = config or EmbeddingConfig.from_env()
        self._client = httpx.Client(timeout=self.config.request_timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> YandexEmbeddings:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _model_uri(self, kind: EmbeddingKind) -> str:
        model = (
            self.config.doc_model if kind == "document" else self.config.query_model
        )
        return f"emb://{self.config.folder_id}/{model}"

    def embed_one(self, text: str, *, kind: EmbeddingKind = "document") -> list[float]:
        payload = {"modelUri": self._model_uri(kind), "text": text}
        headers = {"Authorization": f"Api-Key {self.config.api_key}"}

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = self._client.post(
                    self.config.base_url,
                    headers=headers,
                    json=payload,
                )
                if response.status_code == 429:
                    wait = self.config.retry_delay * (attempt + 2)
                    print(f"  rate limit, waiting {wait:.0f}s...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")
                if not embedding:
                    raise ValueError(f"Empty embedding in response: {data}")
                return [float(value) for value in embedding]
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < self.config.max_retries:
                    time.sleep(self.config.retry_delay * (attempt + 1))
        raise RuntimeError(f"Embedding request failed after retries: {last_error}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        total = len(texts)
        for index, text in enumerate(texts, start=1):
            vectors.append(self.embed_one(text, kind="document"))
            if self.config.batch_pause:
                time.sleep(self.config.batch_pause)
            if index % 50 == 0 or index == total:
                print(f"  embedded {index}/{total}")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_one(text, kind="query")
