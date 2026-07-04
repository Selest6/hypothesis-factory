from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

FEEDBACK_PATH = Path(__file__).resolve().parents[2] / "data" / "feedback.json"


def save_feedback(
    case_id: str,
    hypothesis_title: str,
    rating: str,
    comment: str = "",
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries: list = []
    if FEEDBACK_PATH.exists():
        entries = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    entry: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "case_id": case_id,
        "hypothesis_title": hypothesis_title,
        "rating": rating,
        "comment": comment,
    }
    if extra:
        entry.update(extra)
    entries.append(entry)
    FEEDBACK_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def load_feedback_entries() -> list[dict[str, Any]]:
    if not FEEDBACK_PATH.exists():
        return []
    return json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))


def format_feedback_lessons(case_id: str, limit: int = 8) -> str:
    negative = [
        e
        for e in load_feedback_entries()
        if e.get("rating") == "down" and str(e.get("comment", "")).strip()
    ]
    if not negative:
        return ""
    same_case = [e for e in negative if e.get("case_id") == case_id]
    other = [e for e in negative if e.get("case_id") != case_id]
    chosen = (same_case + other)[-limit:]
    lines = ["Уроки из прошлых замечаний пользователя (учитывай при улучшении):"]
    for e in chosen:
        title = str(e.get("hypothesis_title", ""))[:80]
        comment = str(e.get("comment", "")).strip()
        cid = e.get("case_id", "")
        lines.append(f"- [{cid}] «{title}»: {comment}")
    return "\n".join(lines)
