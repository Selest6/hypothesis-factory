from __future__ import annotations

from pathlib import Path

import fitz

from src.etl.yandex_ocr import YandexOCRClient
from src.models.schemas import SourceRef, TextChunk

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MIN_PAGE_TEXT_LEN = 100
PDF_RENDER_DPI = 150
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


def page_needs_ocr(text: str) -> bool:
    return len(text.strip()) < MIN_PAGE_TEXT_LEN


def _split_text(
    text: str,
    *,
    chunk_id_prefix: str,
    source_file: str,
    page: int | None,
    chunk_type: str,
    metadata: dict,
) -> list[TextChunk]:
    if not text.strip():
        return []

    chunks: list[TextChunk] = []
    start = 0
    part_num = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            split_at = text.rfind("\n", start, end)
            if split_at <= start:
                split_at = text.rfind(" ", start, end)
            if split_at > start:
                end = split_at

        piece = text[start:end].strip()
        if piece:
            part_num += 1
            suffix = f"_p{page}" if page is not None else ""
            part_suffix = f"_{part_num}" if part_num > 1 or end < len(text) else ""
            chunks.append(
                TextChunk(
                    chunk_id=f"{chunk_id_prefix}{suffix}{part_suffix}",
                    text=piece,
                    source=SourceRef(
                        file=source_file,
                        page=page,
                        fragment=piece[:120],
                    ),
                    chunk_type=chunk_type,
                    metadata={**metadata, "part": part_num},
                )
            )

        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks


def ocr_image(path: Path, ocr: YandexOCRClient) -> list[TextChunk]:
    path = Path(path)
    text = ocr.recognize_file(path)
    return _split_text(
        text,
        chunk_id_prefix=f"ocr_{path.stem}",
        source_file=path.name,
        page=None,
        chunk_type="ocr",
        metadata={"source_type": "image", "ocr_model": "page"},
    )


def _render_page_png(doc: fitz.Document, page_idx: int) -> bytes:
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
    return pix.tobytes("png")


def ocr_pdf_page(path: Path, page_num: int, ocr: YandexOCRClient) -> list[TextChunk]:
    path = Path(path)
    doc = fitz.open(path)
    png_bytes = _render_page_png(doc, page_num - 1)
    doc.close()
    text = ocr.recognize_bytes(png_bytes, mime_type="image/png")
    return _split_text(
        text,
        chunk_id_prefix=f"ocr_{path.stem}",
        source_file=path.name,
        page=page_num,
        chunk_type="ocr",
        metadata={"source_type": "pdf_page", "ocr_model": "page"},
    )


def ocr_pdf_missing_pages(path: Path, ocr: YandexOCRClient) -> list[TextChunk]:
    path = Path(path)
    doc = fitz.open(path)
    chunks: list[TextChunk] = []

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page_text = doc[page_idx].get_text("text")
        if not page_needs_ocr(page_text):
            continue

        png_bytes = _render_page_png(doc, page_idx)
        text = ocr.recognize_bytes(png_bytes, mime_type="image/png")
        chunks.extend(
            _split_text(
                text,
                chunk_id_prefix=f"ocr_{path.stem}",
                source_file=path.name,
                page=page_num,
                chunk_type="ocr",
                metadata={"source_type": "pdf_page", "ocr_model": "page"},
            )
        )

    doc.close()
    return chunks


def collect_ocr_targets(data_root: Path) -> tuple[list[Path], list[Path]]:
    data_root = Path(data_root)
    images = sorted(
        p for p in data_root.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )

    pdfs_needing_ocr: list[Path] = []
    for pdf_path in sorted(data_root.rglob("*.pdf")):
        doc = fitz.open(pdf_path)
        needs_any = any(
            page_needs_ocr(doc[page_idx].get_text("text"))
            for page_idx in range(len(doc))
        )
        doc.close()
        if needs_any:
            pdfs_needing_ocr.append(pdf_path)

    return images, pdfs_needing_ocr
