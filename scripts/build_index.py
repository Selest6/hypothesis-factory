#!/usr/bin/env python3
"""Build ChromaDB index from precomputed embeddings.json (no re-embedding)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from src.rag.retriever import ChromaRetriever


def main() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Load embeddings.json into ChromaDB.")
    parser.add_argument(
        "--embeddings-file",
        type=Path,
        default=ROOT / "data" / "processed" / "embeddings.json",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=ROOT / "data" / "chroma",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing collection before indexing",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=128,
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Optional test query (uses Yandex API for query embedding)",
    )
    parser.add_argument(
        "--case-id",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )
    args = parser.parse_args()

    if not args.embeddings_file.exists():
        raise SystemExit(f"Embeddings file not found: {args.embeddings_file.resolve()}")

    items = ChromaRetriever.load_embeddings_file(args.embeddings_file)
    if not items:
        raise SystemExit(f"No items in {args.embeddings_file}")

    print(f"Loading {len(items)} precomputed embeddings into ChromaDB...")

    retriever = ChromaRetriever(persist_dir=args.chroma_dir)
    if args.reset:
        retriever.reset()

    indexed = retriever.upsert_precomputed(items, batch_size=args.batch_size)

    def _repo_relative(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(ROOT))
        except ValueError:
            return str(path)

    manifest = {
        "embeddings_file": _repo_relative(args.embeddings_file),
        "chroma_dir": _repo_relative(args.chroma_dir),
        "document_count": indexed,
        "collection_count": retriever.count(),
    }
    manifest_path = args.chroma_dir / "index_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Chroma dir:      {args.chroma_dir.resolve()}")
    print(f"Indexed docs:    {indexed}")
    print(f"Collection size: {retriever.count()}")
    print(f"Manifest:        {manifest_path}")

    if args.query:
        results = retriever.query(args.query, top_k=args.top_k, case_id=args.case_id)
        print("\nTest query results:")
        for item in results:
            print(
                f"- score={item.score:.3f} "
                f"type={item.metadata.get('doc_type')} "
                f"case={item.metadata.get('case_id')} "
                f"file={item.metadata.get('source_file')}"
            )
            print(f"  {item.text[:180]}...")


if __name__ == "__main__":
    main()
