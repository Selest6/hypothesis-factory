from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"


def load_format_examples(
    case_id: str,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    *,
    max_items: int = 3,
) -> str:
    """Load organizer hypothesis titles as prompt style examples (not RAG / not graph)."""
    path = Path(processed_dir) / "cases" / case_id / "hypotheses.json"
    if not path.exists():
        return ""

    raw = json.loads(path.read_text(encoding="utf-8"))
    titles = [item.get("title", "").strip() for item in raw if item.get("title")]
    if not titles:
        return ""

    lines = [
        "Примеры формулировок от организаторов (уровень конкретности и стиль технолога; "
        "не копируй содержание — строй новые гипотезы из Excel и литературы):",
    ]
    for title in titles[:max_items]:
        lines.append(f"- «{title}»")
    return "\n".join(lines)
