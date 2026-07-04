from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from src.rag.embeddings import YandexEmbeddings


@dataclass
class RetrievedChunk:
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any]


class ChromaRetriever:
    """Persistent ChromaDB store. Index from precomputed embeddings.json; query via Yandex API."""

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

    def upsert_precomputed(
        self,
        items: list[dict[str, Any]],
        *,
        batch_size: int = 128,
    ) -> int:
        """Load vectors from embeddings.json — no API calls."""
        if not items:
            return 0

        indexed = 0
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            self.collection.upsert(
                ids=[item["doc_id"] for item in batch],
                documents=[item["text"] for item in batch],
                embeddings=[item["embedding"] for item in batch],
                metadatas=[self._sanitize_metadata(item.get("metadata", {})) for item in batch],
            )
            indexed += len(batch)
            print(f"  indexed {indexed}/{len(items)}")
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

    def query_mixed(
        self,
        query_text: str,
        case_id: str,
        *,
        top_k: int = 8,
    ) -> list[RetrievedChunk]:
        """Case triplets/hypotheses + literature/instructions (separate filters)."""
        half = max(top_k // 2, 2)
        merged: dict[str, RetrievedChunk] = {}

        for chunk in self.query(query_text, top_k=half, case_id=case_id):
            merged[chunk.doc_id] = chunk

        for chunk in self.query(
            query_text,
            top_k=half,
            doc_types=["literature", "instruction", "ocr"],
        ):
            merged[chunk.doc_id] = chunk

        if len(merged) < top_k:
            for chunk in self.query(query_text, top_k=top_k):
                merged.setdefault(chunk.doc_id, chunk)

        ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        return ranked[:top_k]

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
    def load_embeddings_file(path: Path) -> list[dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("items", [])

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
