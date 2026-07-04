#!/usr/bin/env python3
"""OCR images and PDF pages missing text; save chunks for RAG indexing."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from src.etl.ocr_parser import (
    collect_ocr_targets,
    ocr_image,
    ocr_pdf_page,
    page_needs_ocr,
)
from src.etl.yandex_ocr import YandexOCRClient, YandexOCRError
from src.models.schemas import TextChunk

DEFAULT_DATA = Path(r"C:\Users\alesi\Downloads\Задача 1\Задача 1")


def find_data_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    for candidate in (ROOT / "data" / "raw", DEFAULT_DATA):
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError("Data directory not found. Pass --data-dir.")


def load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("done_keys", []))


def save_checkpoint(path: Path, done_keys: set[str], chunks: list[TextChunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "done_keys": sorted(done_keys),
                "chunk_count": len(chunks),
                "chunks": [chunk.model_dump() for chunk in chunks],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def update_manifest(processed_dir: Path, ocr_count: int) -> None:
    manifest_path = processed_dir / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ocr_chunk_count"] = ocr_count
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ingest_ocr(
    data_root: Path,
    output_dir: Path,
    *,
    delay_sec: float = 0.2,
    checkpoint_every: int = 5,
) -> list[TextChunk]:
    data_root = data_root.resolve()
    output_dir = output_dir.resolve()
    checkpoint_path = output_dir / "ocr" / "checkpoint.json"
    output_path = output_dir / "ocr" / "chunks.json"

    if checkpoint_path.exists():
        checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        chunks = [TextChunk.model_validate(item) for item in checkpoint_data.get("chunks", [])]
        done_keys = set(checkpoint_data.get("done_keys", []))
    else:
        chunks = []
        done_keys = set()

    images, pdfs = collect_ocr_targets(data_root)
    ocr = YandexOCRClient()
    if not ocr.configured:
        raise YandexOCRError("Set YANDEX_API_KEY and YANDEX_FOLDER_ID in .env")

    print(f"Data root:     {data_root}")
    print(f"Images:        {len(images)}")
    print(f"PDFs w/ gaps:  {len(pdfs)}")
    print(f"Already done:  {len(done_keys)}")
    print()

    processed_since_save = 0

    def mark_done(key: str) -> None:
        nonlocal processed_since_save
        done_keys.add(key)
        processed_since_save += 1
        if processed_since_save >= checkpoint_every:
            save_checkpoint(checkpoint_path, done_keys, chunks)
            processed_since_save = 0

    for image_path in images:
        key = f"img:{image_path.resolve()}"
        if key in done_keys:
            continue
        print(f"OCR image: {image_path.relative_to(data_root)}")
        try:
            new_chunks = ocr_image(image_path, ocr)
            chunks.extend(new_chunks)
            print(f"  -> {len(new_chunks)} chunk(s), {sum(len(c.text) for c in new_chunks)} chars")
            mark_done(key)
        except (YandexOCRError, Exception) as exc:
            print(f"  !! failed: {exc}")
        time.sleep(delay_sec)

    for pdf_path in pdfs:
        doc = fitz.open(pdf_path)
        missing_pages = [
            page_idx + 1
            for page_idx in range(len(doc))
            if page_needs_ocr(doc[page_idx].get_text("text"))
        ]
        doc.close()

        print(f"OCR PDF: {pdf_path.relative_to(data_root)} ({len(missing_pages)} pages)")
        for page_num in missing_pages:
            key = f"pdf:{pdf_path.resolve()}:{page_num}"
            if key in done_keys:
                continue

            try:
                new_chunks = ocr_pdf_page(pdf_path, page_num, ocr)
                chunks.extend(new_chunks)
                text_len = sum(len(c.text) for c in new_chunks)
                if page_num == missing_pages[0] or page_num % 10 == 0 or page_num == missing_pages[-1]:
                    print(
                        f"  page {page_num}/{missing_pages[-1]}: "
                        f"{len(new_chunks)} chunk(s), {text_len} chars"
                    )
                mark_done(key)
            except (YandexOCRError, Exception) as exc:
                print(f"  page {page_num}: failed: {exc}")

            time.sleep(delay_sec)

    save_checkpoint(checkpoint_path, done_keys, chunks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([chunk.model_dump() for chunk in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    update_manifest(output_dir, len(chunks))
    return chunks


def main() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="OCR missing images/PDF pages into RAG chunks.")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "processed",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear OCR checkpoint and re-run from scratch",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        help="Pause between OCR API calls (seconds; Yandex limit ~1 req/s)",
    )
    args = parser.parse_args()

    if args.reset:
        checkpoint = args.output_dir / "ocr" / "checkpoint.json"
        if checkpoint.exists():
            checkpoint.unlink()

    data_root = find_data_root(args.data_dir)
    chunks = ingest_ocr(data_root, args.output_dir, delay_sec=args.delay)

    print()
    print(f"OCR chunks saved: {len(chunks)}")
    print(f"Output: {args.output_dir / 'ocr' / 'chunks.json'}")


if __name__ == "__main__":
    main()
