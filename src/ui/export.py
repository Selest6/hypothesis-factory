from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models.schemas import GeneratedHypothesis, PipelineResult, SourceRef

FEEDBACK_PATH = Path(__file__).resolve().parents[2] / "data" / "feedback.json"


def _format_source(src: SourceRef | dict[str, Any]) -> str:
    if isinstance(src, SourceRef):
        data = src.model_dump()
    else:
        data = src
    parts = [str(data.get("file") or "—")]
    if data.get("sheet"):
        parts.append(f"лист {data['sheet']}")
    if data.get("row"):
        parts.append(f"строка {data['row']}")
    if data.get("page"):
        parts.append(f"стр. {data['page']}")
    line = ", ".join(parts)
    if data.get("fragment"):
        line += f" — {str(data['fragment'])[:160]}"
    return line


def _format_risks(h: GeneratedHypothesis) -> tuple[str, str]:
    risks = h.risks
    if isinstance(risks, dict):
        return str(risks.get("technical", "—")), str(risks.get("economic", "—"))
    if isinstance(risks, list):
        tech = risks[0] if risks else "—"
        econ = risks[1] if len(risks) > 1 else "—"
        return str(tech), str(econ)
    return "—", "—"


def result_to_markdown(result: PipelineResult, constraints: str = "") -> str:
    lines = [
        f"# Фабрика гипотез — {result.case_name}",
        "",
        f"**KPI:** {result.kpi_goal}",
        f"**Ограничения:** {constraints or '—'}",
        f"**Режим:** {result.mode}",
        f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    for i, h in enumerate(result.hypotheses, 1):
        lines.extend(_hypothesis_md_block(h, i))
    return "\n".join(lines)


def _hypothesis_md_block(h: GeneratedHypothesis, index: int) -> list[str]:
    lines = [f"## {index}. {h.title}", "", f"**Формулировка:** {h.full_statement}", ""]
    if h.mechanism:
        lines.extend([f"**Механизм:** {h.mechanism}", ""])
    if h.kpi_impact:
        lines.extend([f"**Влияние на KPI:** {h.kpi_impact}", ""])
    if h.scores:
        s = h.scores
        lines.append(
            f"**Оценки:** итого {s.total:.2f} | новизна {s.novelty:.2f} | "
            f"обоснованность {s.groundedness:.2f} | ценность {s.value:.2f} | риск {s.risk:.2f}"
        )
        lines.append("")
    if h.nearest_reference:
        sim = (h.reference_similarity or 0) * 100
        lines.append(f"**Ближайшая эталонная:** «{h.nearest_reference}» (сходство {sim:.0f}%)")
        lines.append("")
    if h.score_explanations:
        lines.append("**Объяснение оценок:**")
        for key, text in h.score_explanations.items():
            lines.append(f"- {text}")
        lines.append("")
    if h.sources:
        lines.append("**Источники:**")
        for src in h.sources:
            lines.append(f"- {_format_source(src)}")
        lines.append("")
    if h.verification_steps:
        lines.append("**Верификация:**")
        for step in h.verification_steps:
            lines.append(f"- {step}")
        lines.append("")
    tech, econ = _format_risks(h)
    lines.extend([f"**Риски (тех.):** {tech}", f"**Риски (экон.):** {econ}", ""])
    return lines


def result_to_json(result: PipelineResult, constraints: str = "") -> str:
    payload = result.model_dump()
    payload["constraints"] = constraints
    payload["exported_at"] = datetime.now().isoformat()
    return json.dumps(payload, ensure_ascii=False, indent=2)


def save_feedback(case_id: str, hypothesis_title: str, rating: str, comment: str = "") -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries: list = []
    if FEEDBACK_PATH.exists():
        entries = json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    entries.append(
        {
            "timestamp": datetime.now().isoformat(),
            "case_id": case_id,
            "hypothesis_title": hypothesis_title,
            "rating": rating,
            "comment": comment,
        }
    )
    FEEDBACK_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
