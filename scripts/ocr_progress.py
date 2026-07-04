#!/usr/bin/env python3
"""Show OCR ingest progress: processed / total with progress bar."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.etl.ocr_parser import collect_ocr_targets, page_needs_ocr

DEFAULT_DATA = Path(r"C:\Users\alesi\Downloads\Задача 1\Задача 1")
CHECKPOINT = ROOT / "data" / "processed" / "ocr" / "checkpoint.json"


def find_data_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    for candidate in (ROOT / "data" / "raw", DEFAULT_DATA):
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError("Data directory not found.")


def count_total_units(data_root: Path) -> tuple[int, int, int]:
    """Return (images, pdf_pages, total)."""
    import fitz

    images, pdfs = collect_ocr_targets(data_root)
    pdf_pages = 0
    for pdf_path in pdfs:
        doc = fitz.open(pdf_path)
        pdf_pages += sum(
            1
            for page_idx in range(len(doc))
            if page_needs_ocr(doc[page_idx].get_text("text"))
        )
        doc.close()
    return len(images), pdf_pages, len(images) + pdf_pages


def load_done_count() -> int:
    if not CHECKPOINT.exists():
        return 0
    data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return len(data.get("done_keys", []))


def load_chunk_count() -> int:
    if not CHECKPOINT.exists():
        return 0
    data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return int(data.get("chunk_count", 0))


def render_bar(done: int, total: int, width: int = 40) -> str:
    if total <= 0:
        return "[" + "?" * width + "]"
    ratio = min(done / total, 1.0)
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    pct = ratio * 100
    return f"[{bar}] {pct:5.1f}%"


def show_progress(data_root: Path, *, watch: bool = False, interval: float = 5.0) -> None:
    images, pdf_pages, total = count_total_units(data_root)

    while True:
        done = load_done_count()
        chunks = load_chunk_count()
        remaining = max(total - done, 0)

        print(f"\nOCR progress")
        print(f"  Images:      {min(done, images)} / {images}")
        pdf_done = max(0, done - images)
        print(f"  PDF pages:   {min(pdf_done, pdf_pages)} / {pdf_pages}")
        print(f"  Total:       {done} / {total}   (remaining: {remaining})")
        print(f"  RAG chunks:  {chunks}")
        print(f"  {render_bar(done, total)}")

        if not watch or done >= total:
            if done >= total:
                print("\nDone.")
            break

        time.sleep(interval)
        # Move cursor up for refresh (simple re-print)
        if watch:
            print("\033[7A", end="")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show OCR ingest progress bar.")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Refresh every 5 seconds until complete",
    )
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()

    data_root = find_data_root(args.data_dir)
    show_progress(data_root, watch=args.watch, interval=args.interval)


if __name__ == "__main__":
    main()
