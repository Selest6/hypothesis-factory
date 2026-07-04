from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"


@lru_cache(maxsize=4)
def load_reading_guide_text(processed_dir: str = "") -> str:
    """Load organizer 'how to read reports' doc for prompts only (never cite as source)."""
    root = Path(processed_dir) if processed_dir else DEFAULT_PROCESSED
    path = root / "instructions" / "chunks.json"
    if not path.exists():
        return ""

    chunks = json.loads(path.read_text(encoding="utf-8"))
    parts: list[str] = []
    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        if text:
            parts.append(text)
    if not parts:
        return ""

    body = "\n\n".join(parts)
    return (
        "Справочник по чтению Excel-отчётов (метаданные для интерпретации данных, "
        "НЕ источник для цитирования в sources):\n"
        f"{body}"
    )
