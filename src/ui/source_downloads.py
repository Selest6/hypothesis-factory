from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.ui.yandex_disk import fetch_file_from_public_disk

DEFAULT_SOURCES = Path(__file__).resolve().parents[2] / "data" / "sources"
DEFAULT_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
DATA_SOURCE_URL = "https://disk.yandex.ru/d/qE55fooRQGNVVA"
MARKER_FILE = "Хвосты КГМК.xlsx"

_FILE_WITH_EXT = re.compile(
    r"([^/\\,·]+(?:\.(?:xlsx?|xls|pdf|docx?|png|jpe?g|webp)))",
    re.IGNORECASE,
)
_ROW_IN_TEXT = re.compile(r"(?:^|[,·]\s*)строка\s*[:\s]*(\d+)", re.IGNORECASE)
_SHEET_IN_TEXT = re.compile(r'[,·]\s*лист\s+[«"]?([^»,"·]+)[»"]?', re.IGNORECASE)
_PAGE_IN_TEXT = re.compile(r"[,·]\s*стр\.?\s*(\d+)", re.IGNORECASE)


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


def extract_download_filename(raw: str) -> str:
    """Return basename of the original document (row/sheet/page are ignored)."""
    raw = raw.strip()
    if not raw or raw.startswith("http"):
        return raw
    match = _FILE_WITH_EXT.search(raw)
    if match:
        name = match.group(1).strip()
        return Path(name).name
    head = raw.split(",")[0].strip()
    if "." in Path(head).name:
        return Path(head).name
    return head


def split_source_location(source: Any) -> dict[str, Any]:
    """Split file vs row/sheet/page for display; download always uses full file."""
    data = _normalize_source(source)
    raw_file = str(data.get("file") or "").strip()

    row = data.get("row")
    sheet = data.get("sheet")
    page = data.get("page")

    if row is None:
        match = _ROW_IN_TEXT.search(raw_file)
        if match:
            row = int(match.group(1))
    if sheet is None:
        match = _SHEET_IN_TEXT.search(raw_file)
        if match:
            sheet = match.group(1).strip()
    if page is None:
        match = _PAGE_IN_TEXT.search(raw_file)
        if match:
            page = int(match.group(1))

    download_file = extract_download_filename(raw_file)
    display_file = download_file or raw_file.split(",")[0].strip()

    return {
        **data,
        "file": display_file,
        "sheet": sheet,
        "row": row,
        "page": page,
        "fragment": data.get("fragment"),
        "download_file": download_file,
    }


def normalize_source_filename(source: Any) -> str:
    return str(split_source_location(source).get("download_file") or "").strip()


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
    fetch_remote: bool = True,
) -> Path | None:
    filename = filename.strip()
    if not filename or filename.startswith("http"):
        return None

    for base in (Path(sources_dir), Path(raw_dir)):
        if not base.exists():
            continue
        direct = base / filename
        if direct.is_file() and direct.stat().st_size > 0:
            return direct
        target = filename.casefold()
        for path in base.rglob("*"):
            if path.is_file() and path.name.casefold() == target:
                return path

    if fetch_remote:
        fetched = fetch_file_from_public_disk(filename, Path(sources_dir))
        if fetched and fetched.is_file():
            return fetched
    return None


def prepare_source_download(
    source: Any,
    *,
    sources_dir: Path | str = DEFAULT_SOURCES,
    raw_dir: Path | str = DEFAULT_RAW,
    fetch_remote: bool = True,
) -> SourceDownload | None:
    file_name = normalize_source_filename(source)
    if not file_name or file_name.lower() in {"требует верификации", "—", "-"}:
        return None

    path = resolve_original_file(
        file_name,
        sources_dir=sources_dir,
        raw_dir=raw_dir,
        fetch_remote=fetch_remote,
    )
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
