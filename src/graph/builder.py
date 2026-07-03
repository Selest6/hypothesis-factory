from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import networkx as nx

from src.models.schemas import NodeType, Triplet

ELEMENT_ALIASES = {
    "28": "Элемент 28",
    "29": "Элемент 29",
    "элемент 28": "Элемент 28",
    "элемент 29": "Элемент 29",
    "ni": "Элемент 28",
    "cu": "Элемент 29",
    "никель": "Элемент 28",
    "медь": "Элемент 29",
}


def node_id(node_type: str | NodeType, label: str) -> str:
    kind = node_type.value if isinstance(node_type, NodeType) else str(node_type)
    return f"{kind}:{label.strip()}"


def normalize_element(text: str) -> str | None:
    lowered = text.lower().strip()
    for key, canonical in ELEMENT_ALIASES.items():
        if key in lowered:
            return canonical
    if "элемент 28" in lowered or "элемент 29" in lowered:
        m = re.search(r"элемент\s*(\d+)", lowered)
        if m:
            return f"Элемент {m.group(1)}"
    return None


class KnowledgeGraph:
    """NetworkX wrapper with domain helpers for hypothesis retrieval."""

    def __init__(self, graph: nx.MultiDiGraph | None = None) -> None:
        self.graph = graph if graph is not None else nx.MultiDiGraph()

    @property
    def node_count(self) -> int:
        return self.graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def nodes_by_type(self, node_type: NodeType | str) -> list[str]:
        kind = node_type.value if isinstance(node_type, NodeType) else node_type
        return [
            n for n, attrs in self.graph.nodes(data=True)
            if attrs.get("node_type") == kind
        ]

    def reference_hypotheses(self, case_id: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for nid in self.nodes_by_type(NodeType.HYPOTHESIS):
            attrs = self.graph.nodes[nid]
            if case_id and attrs.get("case_id") not in (case_id, None):
                continue
            if attrs.get("is_reference"):
                results.append({"node_id": nid, **attrs})
        results.sort(key=lambda item: item.get("index", 0))
        return results

    def plant_nodes(self, case_id: str | None = None) -> list[str]:
        plants = self.nodes_by_type(NodeType.PLANT)
        if case_id is None:
            return plants
        return [
            n for n in plants
            if self.graph.nodes[n].get("case_id") in (case_id, None)
        ]

    def loss_metrics(
        self,
        case_id: str | None = None,
        element: str | None = None,
        metric_kind: str = "loss_tons",
    ) -> list[dict[str, Any]]:
        """Collect loses_to edges with ton/percent metadata."""
        rows: list[dict[str, Any]] = []
        for u, v, _key, data in self.graph.edges(keys=True, data=True):
            if data.get("predicate") != "loses_to":
                continue
            meta = data.get("metadata") or {}
            if meta.get("metric_kind") != metric_kind:
                continue
            if case_id and data.get("case_id") not in (case_id, None):
                continue
            if element and meta.get("element") != element:
                continue
            rows.append(
                {
                    "subject": self.graph.nodes[u].get("label", u),
                    "subject_id": u,
                    "element": meta.get("element"),
                    "value": meta.get("value"),
                    "unit": meta.get("unit"),
                    "context": meta.get("context"),
                    "source": data.get("source"),
                    "case_id": data.get("case_id"),
                }
            )
        rows.sort(key=lambda row: float(row.get("value") or 0), reverse=True)
        return rows

    def neighbors(
        self,
        start_nodes: Iterable[str],
        max_hops: int = 2,
        predicates: set[str] | None = None,
    ) -> set[str]:
        seen: set[str] = set()
        frontier = set(start_nodes)
        for _ in range(max_hops):
            nxt: set[str] = set()
            for nid in frontier:
                if nid not in self.graph:
                    continue
                seen.add(nid)
                for _u, v, data in self.graph.out_edges(nid, data=True):
                    if predicates and data.get("predicate") not in predicates:
                        continue
                    if v not in seen:
                        nxt.add(v)
                for u, _v, data in self.graph.in_edges(nid, data=True):
                    if predicates and data.get("predicate") not in predicates:
                        continue
                    if u not in seen:
                        nxt.add(u)
            frontier = nxt
        return seen

    def context_bundle(
        self,
        case_id: str,
        kpi_goal: str = "",
        max_hops: int = 2,
        max_triplets: int = 40,
    ) -> dict[str, Any]:
        """Build structured context for LLM prompt (graph neighbors + KPI losses)."""
        element = normalize_element(kpi_goal) or "Элемент 28"
        start: set[str] = set(self.plant_nodes(case_id))
        for nid in self.nodes_by_type(NodeType.ELEMENT):
            if self.graph.nodes[nid].get("label") == element:
                start.add(nid)
        for row in self.loss_metrics(case_id=case_id, element=element)[:5]:
            start.add(row["subject_id"])

        visited = self.neighbors(start, max_hops=max_hops)
        edge_facts: list[str] = []
        for u, v, data in self.graph.edges(data=True):
            if u not in visited and v not in visited:
                continue
            if data.get("case_id") not in (case_id, None):
                continue
            subj = self.graph.nodes[u].get("label", u)
            obj = self.graph.nodes[v].get("label", v)
            pred = data.get("predicate", "related_to")
            meta = data.get("metadata") or {}
            extra = ""
            if meta.get("value") is not None:
                extra = f" ({meta.get('value')} {meta.get('unit', '')})".strip()
            edge_facts.append(f"- ({subj}) —[{pred}]→ ({obj}){extra}")
            if len(edge_facts) >= max_triplets:
                break

        top_losses = self.loss_metrics(case_id=case_id, element=element)[:8]
        ref_hyps = self.reference_hypotheses(case_id=case_id)

        return {
            "case_id": case_id,
            "kpi_element": element,
            "graph_triplets": edge_facts,
            "top_losses": top_losses,
            "reference_hypotheses": [h.get("label") for h in ref_hyps],
            "node_count": len(visited),
        }

    def to_json(self) -> dict[str, Any]:
        return nx.node_link_data(self.graph)

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> KnowledgeGraph:
        return cls(nx.node_link_graph(payload, directed=True, multigraph=True))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_json(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> KnowledgeGraph:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_json(payload)


class GraphBuilder:
    """Build a knowledge graph from unified triplets."""

    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()

    def add_triplet(self, triplet: Triplet | dict[str, Any]) -> None:
        if isinstance(triplet, Triplet):
            data = triplet.model_dump()
        else:
            data = triplet

        subj = data["subject"]
        obj = data["object"]
        subj_type = data["subject_type"]
        obj_type = data["object_type"]
        predicate = data["predicate"]
        case_id = data.get("case_id")
        source = data.get("source") or {}
        metadata = data.get("metadata") or {}

        sid = node_id(subj_type, subj)
        oid = node_id(obj_type, obj)

        self.graph.add_node(
            sid,
            label=subj,
            node_type=subj_type,
            case_id=case_id,
        )
        self.graph.add_node(
            oid,
            label=obj,
            node_type=obj_type,
            case_id=case_id,
            is_reference=(predicate == "has_reference_hypothesis"),
            index=metadata.get("index") if predicate == "has_reference_hypothesis" else None,
        )
        self.graph.add_edge(
            sid,
            oid,
            predicate=predicate,
            case_id=case_id,
            source=source,
            metadata=metadata,
        )

        if predicate == "loses_to" and metadata.get("element"):
            element_id = node_id(NodeType.ELEMENT, metadata["element"])
            self.graph.add_node(
                element_id,
                label=metadata["element"],
                node_type=NodeType.ELEMENT.value,
                case_id=case_id,
            )
            self.graph.add_edge(
                sid,
                element_id,
                predicate="loses_element",
                case_id=case_id,
                source=source,
                metadata=metadata,
            )

        if source.get("file"):
            src_id = node_id(NodeType.SOURCE, source["file"])
            self.graph.add_node(
                src_id,
                label=source["file"],
                node_type=NodeType.SOURCE.value,
                case_id=case_id,
            )
            self.graph.add_edge(
                src_id,
                sid,
                predicate="supports",
                case_id=case_id,
                source=source,
                metadata={"fragment": source.get("fragment")},
            )

    def add_triplets(self, triplets: Iterable[Triplet | dict[str, Any]]) -> None:
        for triplet in triplets:
            self.add_triplet(triplet)

    def build(
        self,
        triplets: Iterable[Triplet | dict[str, Any]],
        link_similar_hypotheses: bool = True,
    ) -> KnowledgeGraph:
        self.graph = nx.MultiDiGraph()
        self.add_triplets(triplets)
        if link_similar_hypotheses:
            self._link_similar_hypotheses()
        return KnowledgeGraph(self.graph)

    def _link_similar_hypotheses(self, threshold: float = 0.55) -> None:
        from difflib import SequenceMatcher

        hyp_nodes = [
            (nid, self.graph.nodes[nid].get("label", ""))
            for nid in self.graph.nodes
            if self.graph.nodes[nid].get("node_type") == NodeType.HYPOTHESIS.value
        ]
        for i, (a_id, a_text) in enumerate(hyp_nodes):
            for b_id, b_text in hyp_nodes[i + 1:]:
                if self.graph.nodes[a_id].get("case_id") != self.graph.nodes[b_id].get("case_id"):
                    continue
                ratio = SequenceMatcher(None, a_text.lower(), b_text.lower()).ratio()
                if ratio >= threshold:
                    self.graph.add_edge(
                        a_id,
                        b_id,
                        predicate="similar_to",
                        similarity=round(ratio, 3),
                    )

    @classmethod
    def from_triplets_file(cls, path: Path) -> KnowledgeGraph:
        payload = json.loads(path.read_text(encoding="utf-8"))
        builder = cls()
        return builder.build(payload)

    @classmethod
    def from_processed_dir(cls, processed_dir: Path, case_id: str | None = None) -> KnowledgeGraph:
        processed_dir = Path(processed_dir)
        triplets: list[dict[str, Any]] = []
        if case_id:
            path = processed_dir / "cases" / case_id / "triplets.json"
            if not path.exists():
                raise FileNotFoundError(path)
            triplets = json.loads(path.read_text(encoding="utf-8"))
        else:
            all_path = processed_dir / "all_triplets.json"
            if all_path.exists():
                triplets = json.loads(all_path.read_text(encoding="utf-8"))
            else:
                for case_path in sorted((processed_dir / "cases").glob("*/triplets.json")):
                    triplets.extend(json.loads(case_path.read_text(encoding="utf-8")))
        builder = cls()
        return builder.build(triplets)
