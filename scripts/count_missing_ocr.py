#!/usr/bin/env python3
"""Count content not yet in RAG that would need OCR."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import fitz

ROOT = Path(r"C:\Users\alesi\Downloads\Задача 1\Задача 1")
PROCESSED = Path(
    r"C:\Users\alesi\Downloads\hypothesis-factory-main\hypothesis-factory-main\data\processed\literature\chunks.json"
)


def page_needs_ocr(text: str) -> bool:
    return len(text.strip()) < 100


def main() -> None:
    chunks = json.loads(PROCESSED.read_text(encoding="utf-8"))
    by_file: dict[str, dict] = defaultdict(lambda: {"chunks": 0, "chars": 0})
    for c in chunks:
        f = c.get("source", {}).get("file", "?")
        by_file[f]["chunks"] += 1
        by_file[f]["chars"] += len(c.get("text", ""))

    img_ext = {".png", ".jpg", ".jpeg", ".webp"}
    standalone = sorted(
        p for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in img_ext
    )

    pdf_missing_pages = 0
    pdf_missing_details: list[dict] = []
    figures_on_good_pages = 0  # visual-only, text captions exist

    for pdf_path in sorted(ROOT.rglob("*.pdf")):
        doc = fitz.open(pdf_path)
        empty = short = good = 0
        seen: set[int] = set()
        figs_good = 0
        for page_idx in range(len(doc)):
            t = doc[page_idx].get_text("text")
            if not t.strip():
                empty += 1
            elif len(t.strip()) < 100:
                short += 1
            else:
                good += 1
            needs = page_needs_ocr(t)
            for img in doc[page_idx].get_images(full=True):
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    base = doc.extract_image(xref)
                    w, h = base["width"], base["height"]
                    if w < 50 or h < 50:
                        continue
                    if needs:
                        pass  # counted via page
                    else:
                        figs_good += 1
                except Exception:
                    pass
        n = len(doc)
        doc.close()
        missing = empty + short
        in_rag = by_file.get(pdf_path.name, {"chunks": 0, "chars": 0})
        pdf_missing_details.append(
            {
                "file": pdf_path.name,
                "pages": n,
                "good_text_pages": good,
                "missing_pages": missing,
                "rag_chunks": in_rag["chunks"],
                "rag_chars": in_rag["chars"],
            }
        )
        pdf_missing_pages += missing
        figures_on_good_pages += figs_good

    print("=== IN RAG (literature) ===")
    for f, s in sorted(by_file.items(), key=lambda x: -x[1]["chars"]):
        print(f"  {f}: {s['chunks']} chunks, {s['chars']:,} chars")

    print("\n=== PDF text gaps ===")
    for d in pdf_missing_details:
        status = "OK" if d["missing_pages"] == 0 else "NEEDS OCR"
        print(
            f"  [{status}] {d['file']}: {d['pages']} pp, "
            f"missing={d['missing_pages']}, RAG={d['rag_chunks']} chunks"
        )

    print(f"\nStandalone PNG (never in RAG): {len(standalone)}")
    for p in standalone:
        print(f"  - {p.relative_to(ROOT)}")

    # Practical OCR units
    ocr_png = len(standalone)
    ocr_pdf_pages = pdf_missing_pages
    ocr_total_units = ocr_png + ocr_pdf_pages

    print("\n=== NOT IN RAG — OCR NEEDED ===")
    print(f"  PNG files:              {ocr_png}")
    print(f"  PDF pages w/o text:     {ocr_pdf_pages}")
    print(f"  TOTAL OCR units:        {ocr_total_units}")
    print(f"  (Optional) figure visuals on pages that already have text: {figures_on_good_pages}")

    # Time estimates
    for label, sec in [("fast (~2s/unit)", 2), ("typical (~3s/unit)", 3), ("slow (~5s/unit)", 5)]:
        total_sec = ocr_total_units * sec
        mins = total_sec / 60
        print(f"\n  Time @ {label}: {mins:.0f} min ({total_sec/3600:.1f} h)")


if __name__ == "__main__":
    main()
