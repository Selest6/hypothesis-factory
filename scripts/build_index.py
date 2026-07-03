#!/usr/bin/env python3
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
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

from src.rag.retriever import ChromaRetriever, load_index_documents


def main() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Build ChromaDB index from processed dataset JSON."
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=ROOT / "data" / "processed",
        help="Directory with ingest artifacts (default: data/processed)",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=ROOT / "data" / "chroma",
        help="Persistent ChromaDB directory (default: data/chroma)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing collection before indexing",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Upsert batch size (default: 64)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Optional test query after indexing",
    )
    parser.add_argument(
        "--case-id",
        type=str,
        default=None,
        help="Optional case filter for test query",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-k for optional test query",
    )
    args = parser.parse_args()

    documents = load_index_documents(args.processed_dir)
    if not documents:
        raise SystemExit(f"No documents found in {args.processed_dir.resolve()}")

    retriever = ChromaRetriever(persist_dir=args.chroma_dir)
    if args.reset:
        retriever.reset()

    indexed = retriever.upsert_documents(documents, batch_size=args.batch_size)

    manifest = {
        "processed_dir": str(args.processed_dir.resolve()),
        "chroma_dir": str(args.chroma_dir.resolve()),
        "document_count": indexed,
        "collection_count": retriever.count(),
    }
    manifest_path = args.chroma_dir / "index_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Processed dir:  {args.processed_dir.resolve()}")
    print(f"Chroma dir:     {args.chroma_dir.resolve()}")
    print(f"Indexed docs:   {indexed}")
    print(f"Collection size:{retriever.count()}")
    print(f"Manifest:       {manifest_path}")

    if args.query:
        results = retriever.query(
            args.query,
            top_k=args.top_k,
            case_id=args.case_id,
        )
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
