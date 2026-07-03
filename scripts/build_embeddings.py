#!/usr/bin/env python3
"""Build Yandex API embeddings from processed dataset (no ChromaDB)."""
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

from src.rag.embeddings import YandexEmbeddings
from src.rag.documents import load_index_documents

CHECKPOINT_EVERY = 50


def load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {"items": [], "done_ids": set()}
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    return {"items": items, "done_ids": {item["doc_id"] for item in items}}


def save_checkpoint(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Generate Yandex embeddings for processed documents."
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=ROOT / "data" / "processed",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "processed" / "embeddings.json",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=ROOT / "data" / "processed" / "embeddings.checkpoint.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Embed only first N documents (for testing)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Ignore checkpoint and start from scratch",
    )
    args = parser.parse_args()

    documents = load_index_documents(args.processed_dir)
    if args.limit is not None:
        documents = documents[: args.limit]

    if not documents:
        raise SystemExit(f"No documents in {args.processed_dir.resolve()}")

    if args.reset and args.checkpoint.exists():
        args.checkpoint.unlink()

    checkpoint = load_checkpoint(args.checkpoint)
    items: list[dict] = checkpoint["items"]
    done_ids = checkpoint["done_ids"]
    pending = [doc for doc in documents if doc.doc_id not in done_ids]

    print(f"Total documents:  {len(documents)}")
    print(f"Already done:     {len(done_ids)}")
    print(f"Remaining:        {len(pending)}")

    if not pending:
        print("Nothing to do — all documents already embedded.")
    else:
        with YandexEmbeddings() as embedder:
            for index, doc in enumerate(pending, start=1):
                vector = embedder.embed_one(doc.text, kind="document")
                items.append(
                    {
                        "doc_id": doc.doc_id,
                        "text": doc.text,
                        "embedding": vector,
                        "metadata": doc.metadata,
                    }
                )
                done_ids.add(doc.doc_id)

                total_done = len(done_ids)
                if index % CHECKPOINT_EVERY == 0 or index == len(pending):
                    payload = {
                        "provider": "yandex",
                        "doc_model": embedder.config.doc_model,
                        "dimension": len(vector),
                        "count": len(items),
                        "items": items,
                    }
                    save_checkpoint(args.checkpoint, payload)
                    print(f"  checkpoint {total_done}/{len(documents)}")

    payload = json.loads(args.checkpoint.read_text(encoding="utf-8"))
    payload["count"] = len(payload["items"])
    save_checkpoint(args.output, payload)
    if args.checkpoint.resolve() != args.output.resolve():
        save_checkpoint(args.checkpoint, payload)

    print(f"Saved: {args.output.resolve()}")
    print(f"Count: {payload['count']}, dim: {payload.get('dimension', '?')}")


if __name__ == "__main__":
    main()
