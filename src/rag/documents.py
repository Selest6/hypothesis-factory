from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.graph.builder import REFERENCE_PREDICATE
from src.models.schemas import TextChunk, Triplet


@dataclass
class IndexDocument:
    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def triplet_to_text(triplet: Triplet) -> str:
    return (
        f"{triplet.subject} ({triplet.subject_type.value}) "
        f"—[{triplet.predicate}]→ "
        f"{triplet.object} ({triplet.object_type.value})"
    )


def load_index_documents(processed_dir: Path) -> list[IndexDocument]:
    processed_dir = processed_dir.resolve()
    documents: list[IndexDocument] = []

    literature_path = processed_dir / "literature" / "chunks.json"
    if literature_path.exists():
        for item in json.loads(literature_path.read_text(encoding="utf-8")):
            chunk = TextChunk.model_validate(item)
            documents.append(
                IndexDocument(
                    doc_id=chunk.chunk_id,
                    text=chunk.text,
                    metadata={
                        "doc_type": "literature",
                        "chunk_type": chunk.chunk_type,
                        "source_file": chunk.source.file,
                        "source_ref": _format_source_ref(chunk.source),
                        "case_id": chunk.case_id or "",
                    },
                )
            )

    # instructions/chunks.json is prompt-only (see reading_guide.py), not indexed in Chroma.

    ocr_path = processed_dir / "ocr" / "chunks.json"
    if ocr_path.exists():
        for item in json.loads(ocr_path.read_text(encoding="utf-8")):
            chunk = TextChunk.model_validate(item)
            page = chunk.source.page
            documents.append(
                IndexDocument(
                    doc_id=chunk.chunk_id,
                    text=chunk.text,
                    metadata={
                        "doc_type": "ocr",
                        "chunk_type": chunk.chunk_type,
                        "source_file": chunk.source.file,
                        "source_ref": _format_source_ref(chunk.source),
                        "case_id": chunk.case_id or "",
                        "page": page if page is not None else -1,
                    },
                )
            )

    cases_dir = processed_dir / "cases"
    if cases_dir.exists():
        for case_dir in sorted(cases_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            case_id = case_dir.name

            triplets_path = case_dir / "triplets.json"
            if triplets_path.exists():
                for index, item in enumerate(
                    json.loads(triplets_path.read_text(encoding="utf-8"))
                ):
                    triplet = Triplet.model_validate(item)
                    if triplet.predicate == REFERENCE_PREDICATE:
                        continue
                    digest = hashlib.sha1(
                        triplet.model_dump_json().encode("utf-8")
                    ).hexdigest()[:16]
                    doc_id = f"triplet_{case_id}_{index}_{digest}"
                    documents.append(
                        IndexDocument(
                            doc_id=doc_id,
                            text=triplet_to_text(triplet),
                            metadata={
                                "doc_type": "triplet",
                                "case_id": case_id,
                                "predicate": triplet.predicate,
                                "source_file": triplet.source.file,
                                "source_ref": _format_source_ref(triplet.source),
                            },
                        )
                    )

    return documents


def _format_source_ref(source) -> str:
    parts: list[str] = []
    if source.sheet:
        parts.append(f" sheet={source.sheet}")
    if source.row is not None:
        parts.append(f" row={source.row}")
    if source.page is not None:
        parts.append(f" page={source.page}")
    if source.fragment:
        parts.append(f" fragment={source.fragment[:120]}")
    return "".join(parts)
