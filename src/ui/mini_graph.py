from __future__ import annotations

import tempfile
from pathlib import Path

from pyvis.network import Network

from src.graph.builder import GraphBuilder, normalize_element

PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"

NODE_COLORS = {
    "Plant": "#64748b",
    "Material": "#3b82f6",
    "Element": "#ef4444",
    "SizeClass": "#a78bfa",
    "Mineral": "#10b981",
    "Metric": "#f59e0b",
    "Process": "#06b6d4",
    "Equipment": "#8b5cf6",
    "Hypothesis": "#ec4899",
    "Source": "#475569",
}


def build_mini_graph_html(
    case_id: str,
    kpi_goal: str,
    *,
    processed_dir: Path | str = PROCESSED,
    max_nodes: int = 22,
) -> str:
    graph = GraphBuilder.from_processed_dir(processed_dir, case_id=case_id)
    element = normalize_element(kpi_goal) or "Элемент 28"

    start: set[str] = set(graph.plant_nodes(case_id))
    for nid in graph.nodes_by_type("Element"):
        if graph.graph.nodes[nid].get("label") == element:
            start.add(nid)
    for row in graph.loss_metrics(case_id=case_id, element=element)[:5]:
        start.add(row["subject_id"])

    visited = graph.neighbors(start, max_hops=2)
    if len(visited) > max_nodes:
        visited = set(list(visited)[:max_nodes])

    net = Network(
        height="420px",
        width="100%",
        bgcolor="#0f172a",
        font_color="#e2e8f0",
        directed=True,
    )
    net.barnes_hut(gravity=-6000, central_gravity=0.25, spring_length=110)

    for nid in visited:
        if nid not in graph.graph:
            continue
        attrs = graph.graph.nodes[nid]
        label = str(attrs.get("label", nid))[:45]
        ntype = str(attrs.get("node_type", "Node"))
        color = NODE_COLORS.get(ntype, "#94a3b8")
        size = 22 if ntype in ("Element", "Metric", "Material") else 16
        net.add_node(nid, label=label, title=f"{ntype}: {attrs.get('label', nid)}", color=color, size=size)

    edge_count = 0
    for u, v, data in graph.graph.edges(data=True):
        if u not in visited or v not in visited:
            continue
        pred = str(data.get("predicate", "rel"))[:14]
        net.add_edge(u, v, title=pred, label=pred, color="#475569")
        edge_count += 1
        if edge_count >= max_nodes * 2:
            break

    if not visited:
        return "<p style='color:#94a3b8'>Нет узлов для визуализации</p>"

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        net.save_graph(tmp.name)
        return Path(tmp.name).read_text(encoding="utf-8")
