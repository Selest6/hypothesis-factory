#!/usr/bin/env python3
"""Export pipeline results (live, demo, or cache) to JSON and Markdown."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from src.llm.pipeline import load_cache, run_pipeline
from src.models.schemas import GeneratedHypothesis, PipelineResult
from src.rag.context import CASE_DEFAULT_KPI

ALL_CASES = list(CASE_DEFAULT_KPI.keys())


def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")


def _format_source(source: dict | object) -> str:
    if hasattr(source, "model_dump"):
        source = source.model_dump()
    if not isinstance(source, dict):
        return str(source)
    parts = [source.get("file") or "unknown"]
    if source.get("sheet"):
        parts.append(f"лист {source['sheet']}")
    if source.get("row"):
        parts.append(f"строка {source['row']}")
    if source.get("page"):
        parts.append(f"стр. {source['page']}")
    return ", ".join(str(p) for p in parts if p)


def hypothesis_to_markdown(h: GeneratedHypothesis, rank: int) -> str:
    lines = [f"### {rank}. {h.title}"]
    if h.scores:
        s = h.scores
        lines.append(
            f"**Оценки:** новизна {s.novelty:.2f} | обоснованность {s.groundedness:.2f} | "
            f"риск {s.risk:.2f} | ценность {s.value:.2f} | **итого {s.total:.2f}**"
        )
    lines.append("")
    lines.append(h.full_statement)
    if h.mechanism:
        lines.append("")
        lines.append(f"**Механизм:** {h.mechanism}")
    if h.kpi_impact:
        lines.append("")
        lines.append(f"**Влияние на KPI:** {h.kpi_impact}")
    if h.verification_steps:
        lines.append("")
        lines.append("**Шаги проверки:**")
        lines.extend(f"- {step}" for step in h.verification_steps)
    if h.sources:
        lines.append("")
        lines.append("**Источники:**")
        lines.extend(f"- {_format_source(src)}" for src in h.sources)
    if h.risks:
        lines.append("")
        lines.append("**Риски:**")
        lines.extend(f"- {risk}" for risk in h.risks)
    if h.nearest_reference:
        sim = h.reference_similarity or 0.0
        lines.append("")
        lines.append(f"**Ближайшая эталонная гипотеза:** «{h.nearest_reference}» ({sim:.0%})")
    return "\n".join(lines)


def result_to_markdown(result: PipelineResult) -> str:
    lines = [
        f"# {result.case_name} (`{result.case_id}`)",
        "",
        f"**KPI:** {result.kpi_goal}",
        f"**Режим:** {result.mode}",
    ]
    if result.error:
        lines.append(f"**Ошибка (fallback):** {result.error}")
    if result.context_summary:
        backend = result.context_summary.get("retrieval_backend", "n/a")
        lines.append(f"**Retrieval:** {backend}")
    lines.append("")
    lines.append("## Топ гипотез")
    lines.append("")
    for index, hypothesis in enumerate(result.hypotheses, start=1):
        lines.append(hypothesis_to_markdown(hypothesis, index))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export_case(
    case_id: str,
    *,
    mode: str,
    output_dir: Path,
    constraints: str = "",
) -> PipelineResult:
    if mode == "cache":
        cached = load_cache(case_id)
        if not cached:
            raise FileNotFoundError(f"No cache for case {case_id}")
        result = PipelineResult(
            case_id=case_id,
            case_name=case_id,
            kpi_goal=CASE_DEFAULT_KPI.get(case_id, ""),
            mode="demo",
            hypotheses=cached,
        )
    else:
        result = run_pipeline(
            case_id,
            kpi_goal=CASE_DEFAULT_KPI.get(case_id, ""),
            constraints=constraints,
            mode=mode,  # type: ignore[arg-type]
            save_demo_cache=(mode == "live"),
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{case_id}.json"
    md_path = output_dir / f"{case_id}.md"
    json_path.write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(result_to_markdown(result), encoding="utf-8")
    print(f"exported {case_id} -> {json_path.name}, {md_path.name}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Export hypothesis pipeline results")
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument(
        "--mode",
        choices=["live", "demo", "cache"],
        default="demo",
        help="live=API, demo=cache via pipeline, cache=read cache files only",
    )
    parser.add_argument("--output-dir", default=str(ROOT / "data" / "exports"))
    parser.add_argument("--constraints", default="")
    args = parser.parse_args()

    _load_env()
    case_ids = args.case_ids or ALL_CASES
    output_dir = Path(args.output_dir)

    for case_id in case_ids:
        export_case(
            case_id,
            mode=args.mode,
            output_dir=output_dir,
            constraints=args.constraints,
        )


if __name__ == "__main__":
    main()
