from __future__ import annotations

import json
from pathlib import Path

from src.cases import CASE_NAMES, is_all_cases, iter_case_ids

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"


def load_format_examples(
    case_id: str,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    *,
    max_items: int = 3,
) -> str:
    """Load organizer hypothesis titles as prompt style examples (not RAG / not graph)."""
    if is_all_cases(case_id):
        lines = [
            "Примеры формулировок от организаторов (уровень конкретности и стиль технолога; "
            "не копируй содержание — строй новые гипотезы из Excel и литературы):",
        ]
        for cid in iter_case_ids(case_id):
            path = Path(processed_dir) / "cases" / cid / "hypotheses.json"
            if not path.exists():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            titles = [item.get("title", "").strip() for item in raw if item.get("title")]
            for title in titles[:2]:
                lines.append(f"- [{CASE_NAMES.get(cid, cid)}] «{title}»")
        return "\n".join(lines) if len(lines) > 1 else ""

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
