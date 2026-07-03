from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.graph.builder import GraphBuilder
from src.llm.synthesis import build_synthesis_candidates, format_synthesis_hints
from src.rag.chroma_store import get_chroma_retriever

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
    synthesis_hints: str = ""
    retrieval_backend: str = "keyword"
    chroma_doc_count: int = 0

    def to_prompt_dict(self) -> dict:
        return {
            "retrieved_context": self._format_text_chunks(),
            "graph_context": "\n".join(self.graph_triplets),
            "synthesis_hints": self.synthesis_hints,
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
            score_part = ""
            if chunk.get("_score") is not None:
                score_part = f" (score={chunk['_score']:.3f})"
            parts.append(
                f"[{i}] {file_label}{ref}{page_part}{sheet_part}{score_part}\n"
                f"{chunk.get('text', '')[:800]}"
            )
        return "\n\n".join(parts)

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


def _is_reference_chunk(chunk: dict) -> bool:
    src = chunk.get("source") or chunk.get("metadata") or {}
    if isinstance(src, dict) and "source_file" in src:
        file_name = str(src.get("source_file") or "")
    else:
        file_name = str(src.get("file") or "")
    lowered = file_name.lower()
    return "гипотез" in lowered or "hypothesis" in lowered


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


def _chunks_from_chroma(chroma_retriever, kpi_goal: str, case_id: str, max_chunks: int) -> list[dict]:
    text_chunks: list[dict] = []
    for chunk in chroma_retriever.query_mixed(kpi_goal, case_id, top_k=max_chunks):
        metadata = chunk.metadata or {}
        file_name = str(metadata.get("source_file") or "").lower()
        if "гипотез" in file_name or "hypothesis" in file_name:
            continue
        text_chunks.append(
            {
                "text": chunk.text,
                "metadata": metadata,
                "source": {
                    "file": metadata.get("source_file", ""),
                    "sheet": metadata.get("sheet"),
                    "row": metadata.get("row"),
                    "page": metadata.get("page"),
                    "fragment": chunk.text[:120],
                },
                "_score": chunk.score,
            }
        )
    return text_chunks


def _chunks_from_keywords(
    processed_dir: Path,
    case_id: str,
    kpi_goal: str,
    max_chunks: int,
) -> list[dict]:
    query_tokens = _tokenize(kpi_goal)
    query_tokens |= _tokenize("хвосты флотация извлечение потери элемент")
    candidates: list[dict] = []

    for rel_path in ("literature/chunks.json", "instructions/chunks.json"):
        for chunk in _load_json(processed_dir / rel_path):
            if _is_reference_chunk(chunk):
                continue
            text = chunk.get("text", "")
            score = _chunk_score(text, query_tokens)
            if score > 0:
                candidates.append({**chunk, "_score": float(score)})

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
                    "_score": float(score + 1),
                }
            )

    candidates.sort(key=lambda c: c.get("_score", 0), reverse=True)
    text_chunks: list[dict] = []
    seen_text: set[str] = set()
    for chunk in candidates:
        key = chunk.get("text", "")[:120]
        if key in seen_text:
            continue
        seen_text.add(key)
        text_chunks.append(chunk)
        if len(text_chunks) >= max_chunks:
            break
    return text_chunks


def retrieve_context(
    case_id: str,
    kpi_goal: str = "",
    processed_dir: Path | str = DEFAULT_PROCESSED,
    max_chunks: int = 8,
    max_graph_triplets: int = 40,
    chroma_retriever=None,
    use_chroma: bool = True,
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

    retriever = chroma_retriever
    if use_chroma and retriever is None:
        retriever = get_chroma_retriever(auto_build=True)

    text_chunks: list[dict] = []
    backend = "keyword"
    chroma_count = 0

    if retriever is not None:
        try:
            chroma_count = retriever.count()
            if chroma_count > 0:
                text_chunks = _chunks_from_chroma(retriever, kpi_goal, case_id, max_chunks)
                if text_chunks:
                    backend = "chroma"
        except Exception:
            text_chunks = []

    if not text_chunks:
        text_chunks = _chunks_from_keywords(processed_dir, case_id, kpi_goal, max_chunks)

    synthesis = build_synthesis_candidates(case_id, kpi_goal, processed_dir=processed_dir, n_candidates=8)
    hints = format_synthesis_hints(synthesis, max_items=5)

    return RetrievalContext(
        case_id=case_id,
        case_name=case_name,
        kpi_goal=kpi_goal,
        graph_triplets=bundle.get("graph_triplets", []),
        top_losses=bundle.get("top_losses", []),
        text_chunks=text_chunks,
        reference_hypotheses=reference_titles,
        reference_hypothesis_details=refs_raw if isinstance(refs_raw, list) else [],
        synthesis_hints=hints,
        retrieval_backend=backend,
        chroma_doc_count=chroma_count,
    )
