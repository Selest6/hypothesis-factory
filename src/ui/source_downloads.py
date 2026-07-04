from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"
DEFAULT_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
DATA_SOURCE_URL = "https://disk.yandex.ru/d/qE55fooRQGNVVA"

_CHUNK_STORES = (
    "literature/chunks.json",
    "instructions/chunks.json",
    "ocr/chunks.json",
)


@dataclass(frozen=True)
class SourceDownload:
    data: bytes
    filename: str
    mime: str
    kind: str


def _load_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_source(source: Any) -> dict[str, Any]:
    if hasattr(source, "model_dump"):
        return source.model_dump()
    if isinstance(source, dict):
        return source
    return {"file": str(source)}


def _resolve_raw_file(filename: str, raw_dir: Path = DEFAULT_RAW) -> Path | None:
    if not filename or filename.startswith("http") or not raw_dir.exists():
        return None
    target = filename.casefold()
    for path in raw_dir.rglob("*"):
        if path.is_file() and path.name.casefold() == target:
            return path
    return None


def _mime_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return "application/octet-stream"


def _match_triplets(source: dict[str, Any], case_id: str, processed_dir: Path) -> list[dict]:
    file_name = str(source.get("file") or "")
    sheet = source.get("sheet")
    row = source.get("row")
    triplets = _load_json(processed_dir / "cases" / case_id / "triplets.json")
    matched: list[dict] = []
    for item in triplets:
        src = item.get("source") or {}
        if str(src.get("file") or "") != file_name:
            continue
        if sheet and src.get("sheet") != sheet:
            continue
        if row is not None and src.get("row") not in (row, str(row)):
            continue
        matched.append(item)
    if matched:
        return matched
    for item in triplets:
        src = item.get("source") or {}
        if str(src.get("file") or "") == file_name:
            matched.append(item)
    return matched[:40]


def _match_chunks(source: dict[str, Any], processed_dir: Path) -> list[dict]:
    file_name = str(source.get("file") or "")
    page = source.get("page")
    fragment = str(source.get("fragment") or "").strip()
    matched: list[dict] = []

    for rel in _CHUNK_STORES:
        for chunk in _load_json(processed_dir / rel):
            src = chunk.get("source") or {}
            if str(src.get("file") or "") != file_name:
                continue
            if page is not None and src.get("page") not in (page, str(page)):
                continue
            matched.append(chunk)

    if matched:
        return matched[:12]

    if fragment:
        needle = fragment[:80].lower()
        for rel in _CHUNK_STORES:
            for chunk in _load_json(processed_dir / rel):
                text = str(chunk.get("text") or "")
                if needle and needle in text.lower():
                    matched.append(chunk)
                    if len(matched) >= 6:
                        return matched

    for rel in _CHUNK_STORES:
        for chunk in _load_json(processed_dir / rel):
            src = chunk.get("source") or {}
            if str(src.get("file") or "") == file_name:
                matched.append(chunk)
                if len(matched) >= 6:
                    return matched
    return matched


def _build_excerpt_text(source: dict[str, Any], *, case_id: str, processed_dir: Path) -> str:
    file_name = str(source.get("file") or "источник")
    lines = [
        f"# Фрагмент источника: {file_name}",
        "",
        f"Кейс: {case_id}",
    ]
    if source.get("sheet"):
        lines.append(f"Лист: {source['sheet']}")
    if source.get("row"):
        lines.append(f"Строка: {source['row']}")
    if source.get("page"):
        lines.append(f"Страница: {source['page']}")
    if source.get("fragment"):
        lines.extend(["", "## Цитата из гипотезы", str(source["fragment"])])

    lower = file_name.lower()
    if lower.endswith(".xlsx"):
        triplets = _match_triplets(source, case_id, processed_dir)
        lines.extend(["", "## Данные Excel (processed triplets)", ""])
        if triplets:
            for item in triplets[:25]:
                src = item.get("source") or {}
                row = src.get("row")
                lines.append(
                    f"- {item.get('subject')} — {item.get('predicate')} — {item.get('object')}"
                    + (f" (строка {row})" if row else "")
                )
        else:
            lines.append("Нет совпадающих triplets для этого файла.")
    else:
        chunks = _match_chunks(source, processed_dir)
        lines.extend(["", "## Фрагмент из базы знаний", ""])
        if chunks:
            for chunk in chunks:
                src = chunk.get("source") or {}
                page = src.get("page")
                page_part = f", стр. {page}" if page else ""
                lines.append(f"### Фрагмент{page_part}")
                lines.append(str(chunk.get("text") or "").strip())
                lines.append("")
        else:
            lines.append("Фрагмент в processed-данных не найден.")

    lines.extend(
        [
            "",
            "---",
            f"Оригинальный файл недоступен на сервере. Полный датасет: {DATA_SOURCE_URL}",
        ]
    )
    return "\n".join(lines)


def _excerpt_filename(source: dict[str, Any]) -> str:
    file_name = str(source.get("file") or "source")
    stem = Path(file_name).stem or "source"
    if source.get("row"):
        return f"{stem}_строка_{source['row']}.txt"
    if source.get("page"):
        return f"{stem}_стр_{source['page']}.txt"
    return f"{stem}_фрагмент.txt"


def prepare_source_download(
    source: Any,
    *,
    case_id: str,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    raw_dir: Path | str = DEFAULT_RAW,
) -> SourceDownload | None:
    data = _normalize_source(source)
    file_name = str(data.get("file") or "").strip()
    if not file_name or file_name.lower() in {"требует верификации", "—"}:
        return None

    processed_dir = Path(processed_dir)
    raw_dir = Path(raw_dir)

    if file_name.startswith("http"):
        text = _build_excerpt_text({**data, "file": file_name}, case_id=case_id, processed_dir=processed_dir)
        text = f"URL: {file_name}\n\n{text}"
        safe = "web_source.txt"
        return SourceDownload(
            data=text.encode("utf-8"),
            filename=safe,
            mime="text/plain; charset=utf-8",
            kind="web",
        )

    raw_path = _resolve_raw_file(file_name, raw_dir)
    if raw_path:
        return SourceDownload(
            data=raw_path.read_bytes(),
            filename=raw_path.name,
            mime=_mime_for_path(raw_path),
            kind="original",
        )

    excerpt = _build_excerpt_text(data, case_id=case_id, processed_dir=processed_dir)
    return SourceDownload(
        data=excerpt.encode("utf-8"),
        filename=_excerpt_filename(data),
        mime="text/plain; charset=utf-8",
        kind="excerpt",
    )
