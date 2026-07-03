#!/usr/bin/env python3
"""Build NetworkX knowledge graphs from processed triplets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph.builder import GraphBuilder
from src.graph.scorer import HypothesisScorer


def main() -> None:
    parser = argparse.ArgumentParser(description="Build knowledge graph(s) from processed JSON.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=ROOT / "data" / "processed",
    )
    parser.add_argument(
        "--case-id",
        type=str,
        default=None,
        help="Build graph for one case (default: all cases combined)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "processed" / "graphs",
    )
    args = parser.parse_args()

    kg = GraphBuilder.from_processed_dir(args.processed_dir, case_id=args.case_id)
    out_name = args.case_id or "all"
    graph_path = args.output_dir / f"{out_name}.graph.json"
    kg.save(graph_path)

    summary = {
        "case_id": out_name,
        "nodes": kg.node_count,
        "edges": kg.edge_count,
        "reference_hypotheses": len(kg.reference_hypotheses(args.case_id)),
        "plants": [kg.graph.nodes[n].get("label") for n in kg.plant_nodes(args.case_id)],
        "top_losses_el28": kg.loss_metrics(args.case_id, "Элемент 28")[:3],
    }

    summary_path = args.output_dir / f"{out_name}.summary.json"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Graph saved:   {graph_path}")
    print(f"Summary saved: {summary_path}")
    print(f"Nodes: {kg.node_count}, edges: {kg.edge_count}")

    if args.case_id:
        ctx = kg.context_bundle(args.case_id, kpi_goal="снизить потери элемента 28")
        print(f"Context triplets for LLM: {len(ctx['graph_triplets'])}")
        scorer = HypothesisScorer(kg)
        refs = kg.reference_hypotheses(args.case_id)
        if refs:
            demo = {
                "title": "Тестовая гипотеза: оптимизация классификации хвостов",
                "full_statement": "Если уменьшить класс крупности в гидроциклонах, то снизятся потери элемента 28 в хвостах.",
                "sources": [{"file": "Хвосты НОФ мед.xlsx", "fragment": "хвосты"}],
            }
            print("Demo scores:", scorer.score_hypothesis(demo, case_id=args.case_id, kpi_goal="элемент 28"))


if __name__ == "__main__":
    main()
