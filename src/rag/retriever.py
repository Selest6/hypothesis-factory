from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from src.models.schemas import ReferenceHypothesis, TextChunk, Triplet
from src.rag.embeddings import YandexEmbeddings


@dataclass
class IndexDocument:
    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any]


def triplet_to_text(triplet: Triplet) -> str:
    return (
        f"{triplet.subject} ({triplet.subject_type.value}) "
        f"—[{triplet.predicate}]→ "
        f"{triplet.object} ({triplet.object_type.value})"
    )


def hypothesis_to_text(hypothesis: ReferenceHypothesis) -> str:
    return hypothesis.title


class ChromaRetriever:
    """Persistent ChromaDB store with Yandex embeddings."""

    COLLECTION_NAME = "hypothesis_factory"

    def __init__(
        self,
        persist_dir: Path,
        embedder: YandexEmbeddings | None = None,
    ) -> None:
        self.persist_dir = persist_dir.resolve()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._embedder = embedder
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._collection: Collection | None = None

    @property
    def embedder(self) -> YandexEmbeddings:
        if self._embedder is None:
            self._embedder = YandexEmbeddings()
        return self._embedder

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def reset(self) -> None:
        try:
            self._client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass
        self._collection = None

    def count(self) -> int:
        return self.collection.count()

    def upsert_documents(
        self,
        documents: list[IndexDocument],
        *,
        batch_size: int = 32,
    ) -> int:
        if not documents:
            return 0

        indexed = 0
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            texts = [doc.text for doc in batch]
            embeddings = self.embedder.embed_documents(texts)
            self.collection.upsert(
                ids=[doc.doc_id for doc in batch],
                documents=texts,
                embeddings=embeddings,
                metadatas=[self._sanitize_metadata(doc.metadata) for doc in batch],
            )
            indexed += len(batch)
        return indexed

    def query(
        self,
        query_text: str,
        *,
        top_k: int = 8,
        case_id: str | None = None,
        doc_types: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        query_embedding = self.embedder.embed_query(query_text)
        where = self._build_where(case_id=case_id, doc_types=doc_types)

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[RetrievedChunk] = []
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for doc_id, text, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=False
        ):
            score = 1.0 - float(distance) if distance is not None else 0.0
            chunks.append(
                RetrievedChunk(
                    doc_id=doc_id,
                    text=text or "",
                    score=score,
                    metadata=metadata or {},
                )
            )
        return chunks

    def format_context(self, chunks: list[RetrievedChunk]) -> str:
        blocks: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            source_file = chunk.metadata.get("source_file", "unknown")
            source_ref = chunk.metadata.get("source_ref", "")
            blocks.append(
                f"[{index}] ({chunk.metadata.get('doc_type', 'text')}) "
                f"{source_file}{source_ref}\n"
                f"score={chunk.score:.3f}\n"
                f"{chunk.text}"
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            else:
                sanitized[key] = json.dumps(value, ensure_ascii=False)
        return sanitized

    @staticmethod
    def _build_where(
        *,
        case_id: str | None,
        doc_types: list[str] | None,
    ) -> dict[str, Any] | None:
        clauses: list[dict[str, Any]] = []
        if case_id:
            clauses.append({"case_id": case_id})
        if doc_types:
            if len(doc_types) == 1:
                clauses.append({"doc_type": doc_types[0]})
            else:
                clauses.append({"doc_type": {"$in": doc_types}})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}


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

    instructions_path = processed_dir / "instructions" / "chunks.json"
    if instructions_path.exists():
        for item in json.loads(instructions_path.read_text(encoding="utf-8")):
            chunk = TextChunk.model_validate(item)
            documents.append(
                IndexDocument(
                    doc_id=chunk.chunk_id,
                    text=chunk.text,
                    metadata={
                        "doc_type": "instruction",
                        "chunk_type": chunk.chunk_type,
                        "source_file": chunk.source.file,
                        "source_ref": _format_source_ref(chunk.source),
                        "case_id": chunk.case_id or "",
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

            hypotheses_path = case_dir / "hypotheses.json"
            if hypotheses_path.exists():
                for item in json.loads(hypotheses_path.read_text(encoding="utf-8")):
                    hypothesis = ReferenceHypothesis.model_validate(item)
                    documents.append(
                        IndexDocument(
                            doc_id=f"hypothesis_{case_id}_{hypothesis.index}",
                            text=hypothesis_to_text(hypothesis),
                            metadata={
                                "doc_type": "hypothesis",
                                "case_id": case_id,
                                "source_file": hypothesis.source.file,
                                "source_ref": _format_source_ref(hypothesis.source),
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
