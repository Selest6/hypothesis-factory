#!/usr/bin/env python3
"""Build demo cache for all cases (live API or offline from KPI data)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.scorer import ScoreWeights
from src.llm.pipeline import rank_hypotheses, save_cache
from src.models.schemas import GeneratedHypothesis, SourceRef
from src.rag.context import CASE_DEFAULT_KPI, retrieve_context
from src.ui.presets import CASE_PRESETS

CASE_IDS = list(CASE_PRESETS.keys())


def build_offline_case(case_id: str) -> list[GeneratedHypothesis]:
    """Data-driven demo cache without LLM — from top KPI losses."""
    preset = CASE_PRESETS[case_id]
    kpi_goal = preset.get("kpi_goal") or CASE_DEFAULT_KPI.get(case_id, "")
    ctx = retrieve_context(case_id, kpi_goal)

    raw: list[GeneratedHypothesis] = []
    for i, loss in enumerate(ctx.top_losses[:7], 1):
        src = loss.get("source") or {}
        element = loss.get("element", "металл")
        subject = loss.get("subject", "узел")
        value = loss.get("value", 0)
        unit = loss.get("unit", "т")
        context = loss.get("context") or "хвосты"

        title = f"Снижение потерь {element} для класса «{subject[:40]}»"
        full = (
            f"Если оптимизировать режим обогащения для {subject} ({context}), "
            f"то потери {element} в хвостах снизятся, потому что этот узел даёт "
            f"максимальные потери — {value} {unit} (источник: Excel)."
        )
        raw.append(
            GeneratedHypothesis(
                title=title,
                full_statement=full,
                mechanism=(
                    f"Коррекция параметров на участке {subject} уменьшит некондицию "
                    f"минералов, содержащих {element}, в классе {context}."
                ),
                kpi_impact=f"Потенциальное снижение потерь {element} на участке с {value} {unit}.",
                verification_steps=[
                    f"Сравнить содержание {element} в хвостах до/после изменения режима для {subject}.",
                    "Провести ситовой анализ и минералогию концентрата класса.",
                ],
                sources=[SourceRef.model_validate(src)] if src.get("file") else [],
                risks=[
                    "Изменение режима может повлиять на извлечение в других классах.",
                    "Требуется оценка затрат на реагенты и простои оборудования.",
                ],
            )
        )

    if not raw:
        for ref in ctx.reference_hypothesis_details[:5]:
            src = ref.get("source") or {}
            title = ref.get("title", "Гипотеза")
            raw.append(
                GeneratedHypothesis(
                    title=f"[Demo] {title[:80]}",
                    full_statement=f"Если реализовать «{title}», то потери металла в хвостах снизятся, потому что это направление отражено в эталонном отчёте.",
                    mechanism="Механизм требует уточнения по данным фабрики.",
                    kpi_impact="Ожидаемое снижение потерь в целевом классе крупности.",
                    verification_steps=["Пилотный эксперимент на лабораторной пробе.", "A/B на промышленной секции."],
                    sources=[SourceRef.model_validate(src)] if src.get("file") else [],
                    risks=["Технические ограничения оборудования.", "Экономическая целесообразность."],
                )
            )

    return rank_hypotheses(
        raw,
        case_id=case_id,
        kpi_goal=kpi_goal,
        reference_titles=ctx.reference_hypotheses,
        top_k=5,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build demo cache for hypothesis-factory UI")
    parser.add_argument("--case-id", choices=CASE_IDS, default=None)
    parser.add_argument("--offline", action="store_true", help="Build from KPI losses without API")
    parser.add_argument("--all", action="store_true", default=True)
    args = parser.parse_args()

    cases = [args.case_id] if args.case_id else CASE_IDS

    if args.offline:
        for case_id in cases:
            ranked = build_offline_case(case_id)
            path = save_cache(case_id, ranked, meta={"source": "offline", "kpi_goal": CASE_PRESETS[case_id]["kpi_goal"]})
            print(f"[offline] {case_id}: {len(ranked)} hypotheses -> {path}")
        return

    from src.llm.pipeline import run_pipeline

    for case_id in cases:
        preset = CASE_PRESETS[case_id]
        try:
            result = run_pipeline(
                case_id,
                kpi_goal=preset["kpi_goal"],
                constraints=preset.get("constraints", ""),
                mode="live",
                weights=ScoreWeights(),
                save_demo_cache=True,
            )
            print(f"[live] {case_id}: {len(result.hypotheses)} hypotheses, mode={result.mode}")
        except Exception as exc:
            print(f"[live] {case_id} failed ({exc}), falling back to offline")
            ranked = build_offline_case(case_id)
            save_cache(case_id, ranked, meta={"source": "offline_fallback"})
            print(f"  -> saved {len(ranked)} offline hypotheses")


if __name__ == "__main__":
    main()
