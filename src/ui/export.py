from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src.models.schemas import GeneratedHypothesis, PipelineResult, SourceRef

FEEDBACK_PATH = Path(__file__).resolve().parents[2] / "data" / "feedback.json"
FONT_PATH = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "Arial.ttf"


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
    if h.prior_art_snippet:
        sim = (h.prior_art_similarity or 0) * 100
        lines.append(f"**Ближайший фрагмент литературы:** «{h.prior_art_snippet}» (сходство {sim:.0f}%)")
        lines.append("")
    if h.score_explanations:
        lines.append("**Объяснение оценок:**")
        for text in h.score_explanations.values():
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


def result_to_csv(result: PipelineResult, constraints: str = "") -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "rank",
            "title",
            "full_statement",
            "mechanism",
            "kpi_impact",
            "score_total",
            "novelty",
            "groundedness",
            "value",
            "risk",
            "sources",
            "verification_steps",
            "case_id",
            "kpi_goal",
            "constraints",
        ]
    )
    for i, h in enumerate(result.hypotheses, 1):
        s = h.scores
        sources = "; ".join(_format_source(src) for src in (h.sources or []))
        steps = "; ".join(h.verification_steps or [])
        writer.writerow(
            [
                i,
                h.title,
                h.full_statement,
                h.mechanism or "",
                h.kpi_impact or "",
                f"{s.total:.3f}" if s else "",
                f"{s.novelty:.3f}" if s else "",
                f"{s.groundedness:.3f}" if s else "",
                f"{s.value:.3f}" if s else "",
                f"{s.risk:.3f}" if s else "",
                sources,
                steps,
                result.case_id,
                result.kpi_goal,
                constraints,
            ]
        )
    return buf.getvalue()


def result_to_docx_bytes(result: PipelineResult, constraints: str = "") -> bytes:
    doc = Document()
    doc.add_heading(f"Фабрика гипотез — {result.case_name}", level=0)
    meta = doc.add_paragraph()
    meta.add_run(f"KPI: {result.kpi_goal}\n").bold = True
    meta.add_run(f"Ограничения: {constraints or '—'}\n")
    meta.add_run(f"Режим: {result.mode}\n")
    meta.add_run(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    for i, h in enumerate(result.hypotheses, 1):
        doc.add_heading(f"{i}. {h.title}", level=1)
        p = doc.add_paragraph()
        run = p.add_run(h.full_statement)
        run.italic = True
        if h.mechanism:
            doc.add_paragraph(f"Механизм: {h.mechanism}")
        if h.kpi_impact:
            doc.add_paragraph(f"Влияние на KPI: {h.kpi_impact}")
        if h.scores:
            s = h.scores
            doc.add_paragraph(
                f"Оценки: итого {s.total:.2f} | новизна {s.novelty:.2f} | "
                f"обоснованность {s.groundedness:.2f} | ценность {s.value:.2f} | риск {s.risk:.2f}"
            )
        if h.sources:
            doc.add_paragraph("Источники:", style="List Bullet")
            for src in h.sources:
                doc.add_paragraph(_format_source(src), style="List Bullet")
        if h.verification_steps:
            doc.add_paragraph("Верификация:", style="List Bullet")
            for step in h.verification_steps:
                doc.add_paragraph(step, style="List Bullet")
        tech, econ = _format_risks(h)
        doc.add_paragraph(f"Риски: техн. — {tech}; экон. — {econ}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class _ReportPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_margins(15, 15, 15)
        if FONT_PATH.exists():
            self.add_font("ReportFont", "", str(FONT_PATH))
            self._font = "ReportFont"
        else:
            self._font = "Helvetica"

    def _write_line(self, text: str, size: int = 10, *, bold: bool = False) -> None:
        self.set_font(self._font, size=size + (1 if bold else 0))
        safe = (text or "").replace("\r", "")
        line_height = max(5.0, size * 0.45)
        for paragraph in safe.split("\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                self.ln(line_height * 0.5)
                continue
            self.multi_cell(
                0,
                line_height,
                paragraph,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )

    def write_block(self, title: str, body: str) -> None:
        self._write_line(title, size=12, bold=True)
        self._write_line(body, size=10)
        self.ln(2)


def result_to_pdf_bytes(result: PipelineResult, constraints: str = "") -> bytes:
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf._write_line(f"Фабрика гипотез — {result.case_name}", size=16, bold=True)
    pdf._write_line(f"KPI: {result.kpi_goal}")
    pdf._write_line(f"Ограничения: {constraints or '—'}")
    pdf._write_line(f"Режим: {result.mode}")
    pdf._write_line(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    pdf.ln(4)

    for i, h in enumerate(result.hypotheses, 1):
        pdf._write_line(f"{i}. {h.title}", size=12, bold=True)
        pdf._write_line(h.full_statement)
        if h.mechanism:
            pdf._write_line(f"Механизм: {h.mechanism}")
        if h.kpi_impact:
            pdf._write_line(f"Влияние на KPI: {h.kpi_impact}")
        if h.scores:
            s = h.scores
            pdf._write_line(
                f"Оценки: итого {s.total:.2f} | новизна {s.novelty:.2f} | "
                f"обоснованность {s.groundedness:.2f} | ценность {s.value:.2f} | риск {s.risk:.2f}"
            )
        if h.sources:
            pdf._write_line("Источники:")
            for src in h.sources:
                pdf._write_line(f"  • {_format_source(src)}")
        if h.verification_steps:
            pdf._write_line("Верификация:")
            for step in h.verification_steps:
                pdf._write_line(f"  • {step}")
        tech, econ = _format_risks(h)
        pdf._write_line(f"Риски: техн. — {tech}; экон. — {econ}")
        pdf.ln(4)

    out = pdf.output()
    if isinstance(out, bytes):
        return out
    if isinstance(out, bytearray):
        return bytes(out)
    return str(out).encode("utf-8")


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
