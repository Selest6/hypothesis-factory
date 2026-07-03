#!/usr/bin/env python3
"""Test ChromaDB index build and semantic search."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from src.rag.chroma_store import build_chroma_index, ensure_chroma_index
from src.rag.context import retrieve_context


def main() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Test ChromaDB embeddings index")
    parser.add_argument("--reset", action="store_true", help="Rebuild index from embeddings.json")
    parser.add_argument(
        "--query",
        default="снизить потери меди в хвостах",
        help="Test search query (uses Yandex API for query embedding)",
    )
    parser.add_argument("--case-id", default="nof_med")
    args = parser.parse_args()

    if args.reset:
        retriever = build_chroma_index(reset=True)
    else:
        retriever = ensure_chroma_index()

    if retriever is None:
        raise SystemExit("ChromaDB not available. Check data/processed/embeddings.json")

    print(f"Chroma documents: {retriever.count()}")

    results = retriever.query_mixed(args.query, args.case_id, top_k=5)
    print(f"\nDirect Chroma search ({args.query}):")
    for item in results:
        print(
            f"- score={item.score:.3f} type={item.metadata.get('doc_type')} "
            f"file={item.metadata.get('source_file')}"
        )
        print(f"  {item.text[:150]}...")

    ctx = retrieve_context(args.case_id, args.query, chroma_retriever=retriever)
    print(f"\nretrieve_context backend: {ctx.retrieval_backend}")
    print(f"text chunks: {len(ctx.text_chunks)}")


if __name__ == "__main__":
    main()
