from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.graph.builder import GraphBuilder

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"

CASE_DEFAULT_KPI: dict[str, str] = {
    "kgmk": "снизить потери элемента 28 в хвостах",
    "nof_med": "снизить потери элемента 28 в хвостах",
    "nof_vkr": "снизить потери элемента 28 в хвостах",
    "tof": "снизить потери элемента 28 в хвостах",
}


@dataclass
class RetrievalContext:
    case_id: str
    case_name: str
    kpi_goal: str
    graph_triplets: list[str] = field(default_factory=list)
    top_losses: list[dict] = field(default_factory=list)
    text_chunks: list[dict] = field(default_factory=list)
    reference_hypotheses: list[str] = field(default_factory=list)
    reference_hypothesis_details: list[dict] = field(default_factory=list)

    def to_prompt_dict(self) -> dict:
        return {
            "retrieved_context": self._format_text_chunks(),
            "graph_context": "\n".join(self.graph_triplets),
            "few_shot_examples": self._format_few_shot(),
            "top_losses": self._format_losses(),
        }

    def _format_text_chunks(self) -> str:
        if not self.text_chunks:
            return "Нет дополнительных текстовых фрагментов."
        parts = []
        for i, chunk in enumerate(self.text_chunks, 1):
            src = chunk.get("source") or chunk.get("metadata") or {}
            if isinstance(src, dict) and "source_file" in src:
                file_label = src.get("source_file", "unknown")
                ref = src.get("source_ref", "")
            else:
                file_label = src.get("file", "unknown")
                ref = ""
            page_part = f", стр. {src['page']}" if src.get("page") else ""
            sheet_part = f", лист {src['sheet']}" if src.get("sheet") else ""
            parts.append(
                f"[{i}] {file_label}{ref}{page_part}{sheet_part}\n"
                f"{chunk.get('text', '')[:800]}"
            )
        return "\n\n".join(parts)

    def _format_few_shot(self) -> str:
        if not self.reference_hypotheses:
            return "Нет эталонных гипотез."
        return "\n".join(f"- {title}" for title in self.reference_hypotheses)

    def _format_losses(self) -> str:
        if not self.top_losses:
            return "Нет данных о потерях."
        lines = []
        for row in self.top_losses[:8]:
            src = row.get("source") or {}
            lines.append(
                f"- {row.get('subject')}: {row.get('value')} {row.get('unit', '')} "
                f"({row.get('element')}, {row.get('context')}) "
                f"[{src.get('file', '')}, строка {src.get('row', '?')}]"
            )
        return "\n".join(lines)


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", text.lower()) if len(t) >= 3}


def _chunk_score(text: str, query_tokens: set[str]) -> int:
    if not query_tokens:
        return 0
    return len(_tokenize(text) & query_tokens)


def _load_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def retrieve_context(
    case_id: str,
    kpi_goal: str = "",
    processed_dir: Path | str = DEFAULT_PROCESSED,
    max_chunks: int = 8,
    max_graph_triplets: int = 40,
    chroma_retriever=None,
) -> RetrievalContext:
    processed_dir = Path(processed_dir)
    manifest = _load_json(processed_dir / "manifest.json")
    case_name = case_id
    for case in manifest.get("cases", []):
        if case.get("case_id") == case_id:
            case_name = case.get("case_name", case_id)
            break

    if not kpi_goal:
        kpi_goal = CASE_DEFAULT_KPI.get(case_id, "снизить потери металла в хвостах")

    graph = GraphBuilder.from_processed_dir(processed_dir, case_id=case_id)
    bundle = graph.context_bundle(
        case_id=case_id,
        kpi_goal=kpi_goal,
        max_triplets=max_graph_triplets,
    )

    refs_raw = _load_json(processed_dir / "cases" / case_id / "hypotheses.json")
    reference_titles = [h.get("title", "") for h in refs_raw if h.get("title")]

    text_chunks: list[dict] = []
    if chroma_retriever is not None:
        try:
            for chunk in chroma_retriever.query(kpi_goal, top_k=max_chunks, case_id=case_id):
                text_chunks.append(
                    {
                        "text": chunk.text,
                        "metadata": chunk.metadata,
                        "source": {
                            "file": chunk.metadata.get("source_file", ""),
                            "fragment": chunk.text[:120],
                        },
                        "_score": chunk.score,
                    }
                )
        except Exception:
            text_chunks = []

    if not text_chunks:
        query_tokens = _tokenize(kpi_goal)
        query_tokens |= _tokenize("хвосты флотация извлечение потери элемент")
        candidates: list[dict] = []
        for rel_path in ("literature/chunks.json", "instructions/chunks.json"):
            for chunk in _load_json(processed_dir / rel_path):
                text = chunk.get("text", "")
                score = _chunk_score(text, query_tokens)
                if score > 0:
                    candidates.append({**chunk, "_score": score})

        triplets = _load_json(processed_dir / "cases" / case_id / "triplets.json")
        for triplet in triplets[:200]:
            fragment = (triplet.get("source") or {}).get("fragment") or ""
            subj = triplet.get("subject", "")
            obj = triplet.get("object", "")
            text = f"{subj} {triplet.get('predicate', '')} {obj} {fragment}"
            score = _chunk_score(text, query_tokens)
            if score >= 2:
                candidates.append(
                    {
                        "text": text[:600],
                        "source": triplet.get("source"),
                        "case_id": case_id,
                        "_score": score + 1,
                    }
                )

        candidates.sort(key=lambda c: c.get("_score", 0), reverse=True)
        seen_text: set[str] = set()
        for chunk in candidates:
            key = chunk.get("text", "")[:120]
            if key in seen_text:
                continue
            seen_text.add(key)
            text_chunks.append(chunk)
            if len(text_chunks) >= max_chunks:
                break

    return RetrievalContext(
        case_id=case_id,
        case_name=case_name,
        kpi_goal=kpi_goal,
        graph_triplets=bundle.get("graph_triplets", []),
        top_losses=bundle.get("top_losses", []),
        text_chunks=text_chunks,
        reference_hypotheses=reference_titles,
        reference_hypothesis_details=refs_raw if isinstance(refs_raw, list) else [],
    )
