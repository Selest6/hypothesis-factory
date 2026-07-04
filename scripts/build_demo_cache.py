#!/usr/bin/env python3
"""Build demo cache for all cases (live API or synthesis from KPI data)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.scorer import ScoreWeights
from src.llm.pipeline import rank_hypotheses, save_cache
from src.llm.synthesis import build_synthesis_candidates
from src.rag.context import CASE_DEFAULT_KPI, retrieve_context
from src.ui.presets import CASE_PRESETS

CASE_IDS = list(CASE_PRESETS.keys())


def build_offline_case(case_id: str) -> list:
    """Data-driven demo cache: synthesis from Excel + graph + literature."""
    preset = CASE_PRESETS[case_id]
    kpi_goal = preset.get("kpi_goal") or CASE_DEFAULT_KPI.get(case_id, "")
    ctx = retrieve_context(case_id, kpi_goal)

    raw = build_synthesis_candidates(case_id, kpi_goal, n_candidates=7)
    if not raw:
        raise RuntimeError(f"No synthesis candidates for {case_id}")

    return rank_hypotheses(
        raw,
        case_id=case_id,
        kpi_goal=kpi_goal,
        literature_texts=ctx.literature_texts(),
        top_k=5,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build demo cache for hypothesis-factory UI")
    parser.add_argument("--case-id", choices=CASE_IDS, default=None)
    parser.add_argument("--offline", action="store_true", help="Build from synthesis without API")
    parser.add_argument("--all", action="store_true", default=True)
    args = parser.parse_args()

    cases = [args.case_id] if args.case_id else CASE_IDS

    if args.offline:
        for case_id in cases:
            ranked = build_offline_case(case_id)
            path = save_cache(
                case_id,
                ranked,
                meta={"source": "synthesis", "kpi_goal": CASE_PRESETS[case_id]["kpi_goal"]},
            )
            print(f"[synthesis] {case_id}: {len(ranked)} hypotheses -> {path}")
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
            print(f"[live] {case_id} failed ({exc}), falling back to synthesis")
            ranked = build_offline_case(case_id)
            save_cache(case_id, ranked, meta={"source": "synthesis_fallback"})
            print(f"  -> saved {len(ranked)} synthesized hypotheses")


if __name__ == "__main__":
    main()
