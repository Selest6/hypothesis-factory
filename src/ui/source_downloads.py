from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SOURCES = Path(__file__).resolve().parents[2] / "data" / "sources"
DEFAULT_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
DATA_SOURCE_URL = "https://disk.yandex.ru/d/qE55fooRQGNVVA"
MARKER_FILE = "Хвосты КГМК.xlsx"


@dataclass(frozen=True)
class SourceDownload:
    data: bytes
    filename: str
    mime: str


def _normalize_source(source: Any) -> dict[str, Any]:
    if hasattr(source, "model_dump"):
        return source.model_dump()
    if isinstance(source, dict):
        return source
    return {"file": str(source)}


def _mime_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return f"image/{suffix.lstrip('.')}"
    return "application/octet-stream"


def resolve_original_file(
    filename: str,
    *,
    sources_dir: Path | str = DEFAULT_SOURCES,
    raw_dir: Path | str = DEFAULT_RAW,
) -> Path | None:
    if not filename or filename.startswith("http"):
        return None
    target = filename.casefold()
    for base in (Path(sources_dir), Path(raw_dir)):
        if not base.exists():
            continue
        direct = base / filename
        if direct.is_file():
            return direct
        for path in base.rglob("*"):
            if path.is_file() and path.name.casefold() == target:
                return path
    return None


def prepare_source_download(
    source: Any,
    *,
    sources_dir: Path | str = DEFAULT_SOURCES,
    raw_dir: Path | str = DEFAULT_RAW,
) -> SourceDownload | None:
    data = _normalize_source(source)
    file_name = str(data.get("file") or "").strip()
    if not file_name or file_name.lower() in {"требует верификации", "—"}:
        return None
    if file_name.startswith("http"):
        return None

    path = resolve_original_file(file_name, sources_dir=sources_dir, raw_dir=raw_dir)
    if not path:
        return None
    return SourceDownload(
        data=path.read_bytes(),
        filename=path.name,
        mime=_mime_for_path(path),
    )


def list_required_source_files(*, processed_dir: Path | None = None) -> list[str]:
    processed_dir = processed_dir or Path(__file__).resolve().parents[2] / "data" / "processed"
    names: set[str] = set()

    def add(name: str) -> None:
        name = name.strip()
        if not name or "гипотез" in name.lower():
            return
        names.add(name)

    for case_dir in (processed_dir / "cases").glob("*/triplets.json"):
        for item in json.loads(case_dir.read_text(encoding="utf-8")):
            add(str((item.get("source") or {}).get("file") or ""))

    for rel in ("literature/chunks.json", "instructions/chunks.json", "ocr/chunks.json"):
        path = processed_dir / rel
        if not path.exists():
            continue
        for item in json.loads(path.read_text(encoding="utf-8")):
            add(str((item.get("source") or {}).get("file") or ""))

    return sorted(names)
