from __future__ import annotations

from pathlib import Path

import fitz

from src.models.schemas import SourceRef, TextChunk


def parse_pdf(
    path: Path,
    *,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    """Extract text from PDF and split into page-aware chunks for RAG."""
    path = Path(path)
    doc = fitz.open(path)
    chunks: list[TextChunk] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_text = page.get_text("text").strip()
        if not page_text:
            continue

        page_num = page_idx + 1
        start = 0
        part_num = 0

        while start < len(page_text):
            end = min(start + chunk_size, len(page_text))
            if end < len(page_text):
                split_at = page_text.rfind("\n", start, end)
                if split_at <= start:
                    split_at = page_text.rfind(" ", start, end)
                if split_at > start:
                    end = split_at

            text = page_text[start:end].strip()
            if text:
                part_num += 1
                chunks.append(
                    TextChunk(
                        chunk_id=f"{path.stem}_p{page_num}_{part_num}",
                        text=text,
                        source=SourceRef(
                            file=path.name,
                            page=page_num,
                            fragment=text[:120],
                        ),
                        chunk_type="literature",
                        metadata={
                            "page": page_num,
                            "part": part_num,
                            "char_start": start,
                        },
                    )
                )

            if end >= len(page_text):
                break
            start = max(end - chunk_overlap, start + 1)

    doc.close()
    return chunks
