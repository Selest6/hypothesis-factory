from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from src.graph.builder import KnowledgeGraph, normalize_element


@dataclass
class ScoreWeights:
    novelty: float = 0.25
    groundedness: float = 0.30
    risk: float = 0.20
    value: float = 0.25

    def normalized(self) -> ScoreWeights:
        total = self.novelty + self.groundedness + self.risk + self.value
        if total <= 0:
            return ScoreWeights()
        return ScoreWeights(
            novelty=self.novelty / total,
            groundedness=self.groundedness / total,
            risk=self.risk / total,
            value=self.value / total,
        )


class HypothesisScorer:
    """Score generated hypotheses using graph structure and source links."""

    def __init__(self, graph: KnowledgeGraph, weights: ScoreWeights | None = None) -> None:
        self.graph = graph
        self.weights = (weights or ScoreWeights()).normalized()

    def score_hypothesis(
        self,
        hypothesis: dict[str, Any],
        case_id: str,
        kpi_goal: str = "",
    ) -> dict[str, float]:
        novelty = self.score_novelty(hypothesis, case_id)
        groundedness = self.score_groundedness(hypothesis, case_id)
        risk = self.score_risk(hypothesis, case_id)
        value = self.score_value(hypothesis, case_id, kpi_goal=kpi_goal)
        total = (
            novelty * self.weights.novelty
            + groundedness * self.weights.groundedness
            + (1.0 - risk) * self.weights.risk
            + value * self.weights.value
        )
        return {
            "novelty": round(novelty, 3),
            "groundedness": round(groundedness, 3),
            "risk": round(risk, 3),
            "value": round(value, 3),
            "total": round(total, 3),
        }

    def rank(
        self,
        hypotheses: list[dict[str, Any]],
        case_id: str,
        kpi_goal: str = "",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for hyp in hypotheses:
            scores = self.score_hypothesis(hyp, case_id=case_id, kpi_goal=kpi_goal)
            ranked.append({**hyp, "scores": scores})
        ranked.sort(key=lambda item: item["scores"]["total"], reverse=True)
        return ranked[:top_k]

    def score_novelty(self, hypothesis: dict[str, Any], case_id: str) -> float:
        text = self._hypothesis_text(hypothesis)
        refs = self.graph.reference_hypotheses(case_id=case_id)
        if not refs or not text:
            return 0.7

        best_sim = max(
            SequenceMatcher(None, text.lower(), ref.get("label", "").lower()).ratio()
            for ref in refs
        )
        return max(0.0, min(1.0, 1.0 - best_sim))

    def score_groundedness(self, hypothesis: dict[str, Any], case_id: str) -> float:
        sources = hypothesis.get("sources") or []
        if not sources:
            return 0.0

        known_files = {
            self.graph.graph.nodes[n].get("label", "").lower()
            for n in self.graph.nodes_by_type("Source")
        }
        valid = 0
        for src in sources:
            if isinstance(src, dict):
                file_name = (src.get("file") or "").lower()
                fragment = (src.get("fragment") or "").strip()
            else:
                file_name = str(src).lower()
                fragment = ""
            if file_name and any(file_name in known or known in file_name for known in known_files):
                valid += 1
            elif fragment:
                valid += 0.5

        source_score = min(1.0, valid / max(len(sources), 1))

        support_edges = 0
        text = self._hypothesis_text(hypothesis).lower()
        for _u, _v, data in self.graph.graph.edges(data=True):
            if data.get("predicate") != "supports":
                continue
            if data.get("case_id") not in (case_id, None):
                continue
            fragment = ((data.get("source") or {}).get("fragment") or "").lower()
            if fragment and fragment[:20] in text:
                support_edges += 1

        support_score = min(1.0, support_edges / 3.0)
        return min(1.0, 0.7 * source_score + 0.3 * support_score)

    def score_risk(self, hypothesis: dict[str, Any], case_id: str) -> float:
        """Higher = riskier. Penalize contradictions and unsupported numeric claims."""
        risk = 0.15
        text = hypothesis.get("full_statement") or hypothesis.get("title") or ""
        numbers = re.findall(r"\d+(?:[.,]\d+)?", text)
        sources = hypothesis.get("sources") or []
        if numbers and not sources:
            risk += 0.35

        contradictions = self._count_contradictions(case_id)
        if contradictions:
            risk += min(0.4, contradictions * 0.08)

        if "требует верификации" in text.lower():
            risk += 0.1

        return min(1.0, risk)

    def score_value(self, hypothesis: dict[str, Any], case_id: str, kpi_goal: str = "") -> float:
        element = normalize_element(kpi_goal) or normalize_element(self._hypothesis_text(hypothesis))
        if element is None:
            element = "Элемент 28"

        losses = self.graph.loss_metrics(case_id=case_id, element=element, metric_kind="loss_tons")
        if not losses:
            return 0.4

        max_loss = max(float(row.get("value") or 0) for row in losses)
        if max_loss <= 0:
            return 0.4

        mentioned_entities = self._mentioned_entities(hypothesis, case_id)
        if not mentioned_entities:
            top = float(losses[0].get("value") or 0)
            return min(1.0, 0.5 + 0.5 * (top / max_loss))

        best = 0.0
        for row in losses:
            if row["subject"].lower() in mentioned_entities:
                best = max(best, float(row.get("value") or 0))
        if best <= 0:
            best = float(losses[0].get("value") or 0)
        return min(1.0, best / max_loss)

    def _hypothesis_text(self, hypothesis: dict[str, Any]) -> str:
        parts = [
            hypothesis.get("title") or "",
            hypothesis.get("full_statement") or "",
            hypothesis.get("mechanism") or "",
        ]
        return " ".join(p for p in parts if p).strip()

    def _mentioned_entities(self, hypothesis: dict[str, Any], case_id: str) -> set[str]:
        text = self._hypothesis_text(hypothesis).lower()
        entities: set[str] = set()
        for nid in self.graph.graph.nodes:
            attrs = self.graph.graph.nodes[nid]
            if attrs.get("case_id") not in (case_id, None):
                continue
            label = (attrs.get("label") or "").lower()
            if len(label) >= 4 and label in text:
                entities.add(label)
        return entities

    def _count_contradictions(self, case_id: str) -> int:
        """Same subject + element with materially different loss values."""
        buckets: dict[tuple[str, str, str], set[float]] = {}
        for _u, _v, data in self.graph.graph.edges(data=True):
            if data.get("predicate") != "loses_to":
                continue
            if data.get("case_id") not in (case_id, None):
                continue
            meta = data.get("metadata") or {}
            element = meta.get("element")
            value = meta.get("value")
            metric_kind = meta.get("metric_kind")
            context = meta.get("context") or "default"
            if not element or value is None or not metric_kind:
                continue
            subj = self.graph.graph.nodes[_u].get("label", _u)
            key = (subj, element, metric_kind)
            buckets.setdefault(key, set()).add(round(float(value), 3))

        contradictions = 0
        for values in buckets.values():
            if len(values) > 1:
                spread = max(values) - min(values)
                if spread / max(max(values), 1.0) > 0.05:
                    contradictions += 1
        return contradictions
