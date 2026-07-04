from __future__ import annotations

import base64
import os
import time
from typing import Any

import httpx

DEFAULT_OCR_URL = "https://ocr.api.cloud.yandex.net/ocr/v1/recognizeText"

MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".pdf": "application/pdf",
}


class YandexOCRError(RuntimeError):
    pass


class YandexOCRClient:
    """Sync OCR via Yandex Cloud Vision."""

    def __init__(
        self,
        api_key: str | None = None,
        folder_id: str | None = None,
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
        self.timeout = timeout
        self.ocr_url = os.getenv("YANDEX_OCR_URL", DEFAULT_OCR_URL).strip()

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.folder_id)

    def _auth_header(self) -> str:
        if self.api_key.startswith("t1.") or self.api_key.startswith("AQVN"):
            return f"Api-Key {self.api_key}"
        return f"Bearer {self.api_key}"

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        try:
            annotation = data["result"]["textAnnotation"]
        except (KeyError, TypeError) as exc:
            raise YandexOCRError(f"Unexpected OCR response: {data}") from exc

        full_text = annotation.get("fullText")
        if full_text and full_text.strip():
            return full_text.strip()

        lines: list[str] = []
        for block in annotation.get("blocks", []):
            for line in block.get("lines", []):
                words = [word.get("text", "") for word in line.get("words", [])]
                line_text = " ".join(word for word in words if word).strip()
                if line_text:
                    lines.append(line_text)
        return "\n".join(lines).strip()

    def recognize_bytes(
        self,
        content: bytes,
        *,
        mime_type: str = "image/png",
        languages: list[str] | None = None,
        model: str = "page",
    ) -> str:
        if not self.configured:
            raise YandexOCRError(
                "Yandex OCR is not configured. Set YANDEX_API_KEY and YANDEX_FOLDER_ID."
            )

        payload = {
            "mimeType": mime_type,
            "languageCodes": languages or ["ru", "en"],
            "model": model,
            "content": base64.b64encode(content).decode("ascii"),
        }
        headers = {
            "Authorization": self._auth_header(),
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self.timeout) as client:
            last_error: Exception | None = None
            for attempt in range(5):
                try:
                    response = client.post(self.ocr_url, headers=headers, json=payload)
                    if response.status_code == 429:
                        wait = 2.0 * (attempt + 1)
                        time.sleep(wait)
                        continue
                    if response.status_code >= 400:
                        raise YandexOCRError(
                            f"Yandex OCR HTTP {response.status_code}: {response.text[:500]}"
                        )
                    data = response.json()
                    return self._extract_text(data)
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                    last_error = exc
                    time.sleep(2.0 * (attempt + 1))
            if last_error is not None:
                raise YandexOCRError(f"Yandex OCR connection failed: {last_error}") from last_error
            raise YandexOCRError("Yandex OCR failed after retries (rate limit?)")

    def recognize_file(
        self,
        path: str | os.PathLike[str],
        *,
        mime_type: str | None = None,
        languages: list[str] | None = None,
        model: str = "page",
    ) -> str:
        file_path = os.fspath(path)
        suffix = os.path.splitext(file_path)[1].lower()
        resolved_mime = mime_type or MIME_BY_SUFFIX.get(suffix, "image/png")
        content = open(file_path, "rb").read()
        return self.recognize_bytes(
            content,
            mime_type=resolved_mime,
            languages=languages,
            model=model,
        )
