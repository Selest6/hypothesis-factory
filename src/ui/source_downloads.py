from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from src.rag.context import retrieve_context

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"
DEFAULT_RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
DATA_SOURCE_URL = "https://disk.yandex.ru/d/qE55fooRQGNVVA"


@dataclass(frozen=True)
class SourceDocument:
    name: str
    kind: str
    scope: str
    raw_path: Path | None


def _load_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_raw_file(filename: str, raw_dir: Path = DEFAULT_RAW) -> Path | None:
    if not filename or not raw_dir.exists():
        return None
    target = filename.casefold()
    for path in raw_dir.rglob("*"):
        if path.is_file() and path.name.casefold() == target:
            return path
    return None


def _file_kind(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".xlsx"):
        return "excel"
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".docx"):
        return "docx"
    return "file"


def _is_reference_hypothesis_file(name: str) -> bool:
    """Organizer reference hypotheses — not part of LLM knowledge base."""
    lowered = name.lower()
    return "гипотез" in lowered or "hypothesis" in lowered


def list_case_source_documents(
    case_id: str,
    *,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    raw_dir: Path | str = DEFAULT_RAW,
) -> list[SourceDocument]:
    processed_dir = Path(processed_dir)
    raw_dir = Path(raw_dir)
    seen: set[str] = set()
    docs: list[SourceDocument] = []

    def add(name: str, scope: str) -> None:
        name = name.strip()
        if not name or name in seen or _is_reference_hypothesis_file(name):
            return
        seen.add(name)
        docs.append(
            SourceDocument(
                name=name,
                kind=_file_kind(name),
                scope=scope,
                raw_path=_resolve_raw_file(name, raw_dir),
            )
        )

    triplets_path = processed_dir / "cases" / case_id / "triplets.json"
    for item in _load_json(triplets_path):
        src = item.get("source") or {}
        add(str(src.get("file") or ""), f"кейс {case_id}")

    for item in _load_json(processed_dir / "literature" / "chunks.json"):
        src = item.get("source") or {}
        add(str(src.get("file") or ""), "литература (PDF)")

    for item in _load_json(processed_dir / "instructions" / "chunks.json"):
        src = item.get("source") or {}
        add(str(src.get("file") or ""), "инструкции")

    docs.sort(key=lambda d: (d.scope, d.name))
    return docs


def triplets_to_csv_bytes(case_id: str, *, processed_dir: Path | str = DEFAULT_PROCESSED) -> bytes:
    processed_dir = Path(processed_dir)
    triplets = _load_json(processed_dir / "cases" / case_id / "triplets.json")
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "subject",
            "predicate",
            "object",
            "subject_type",
            "object_type",
            "file",
            "sheet",
            "row",
            "page",
            "fragment",
        ],
    )
    writer.writeheader()
    for item in triplets:
        src = item.get("source") or {}
        writer.writerow(
            {
                "subject": item.get("subject"),
                "predicate": item.get("predicate"),
                "object": item.get("object"),
                "subject_type": item.get("subject_type"),
                "object_type": item.get("object_type"),
                "file": src.get("file"),
                "sheet": src.get("sheet"),
                "row": src.get("row"),
                "page": src.get("page"),
                "fragment": src.get("fragment"),
            }
        )
    return buffer.getvalue().encode("utf-8-sig")


def chunks_to_text_bytes(chunks_path: Path, *, title: str) -> bytes:
    chunks = _load_json(chunks_path)
    lines = [f"# {title}", ""]
    current_file = ""
    for chunk in chunks:
        src = chunk.get("source") or {}
        file_name = str(src.get("file") or "unknown")
        if file_name != current_file:
            current_file = file_name
            lines.append(f"\n## {file_name}\n")
        page = src.get("page")
        page_part = f", стр. {page}" if page else ""
        lines.append(f"### Фрагмент{page_part}\n")
        lines.append(str(chunk.get("text") or "").strip())
        lines.append("")
    return "\n".join(lines).encode("utf-8")


def build_llm_context_markdown(
    case_id: str,
    kpi_goal: str,
    *,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    use_web: bool = False,
) -> str:
    context = retrieve_context(
        case_id,
        kpi_goal,
        processed_dir=processed_dir,
        use_chroma=True,
        use_web=use_web,
        include_synthesis_hints=True,
    )
    prompt = context.to_prompt_dict()
    lines = [
        f"# Контекст для LLM — {context.case_name} ({case_id})",
        "",
        f"**KPI:** {context.kpi_goal}",
        f"**Retrieval:** {context.retrieval_backend} · Chroma docs: {context.chroma_doc_count}",
        "",
        "## Топ потери (Excel → граф)",
        prompt.get("top_losses") or "—",
        "",
        "## Граф знаний (фрагмент)",
        prompt.get("graph_context") or "—",
        "",
        "## RAG-фрагменты (Chroma / keyword)",
        prompt.get("retrieved_context") or "—",
        "",
        "## Подсказки синтеза",
        prompt.get("synthesis_hints") or "—",
        "",
        "## Примеры формата",
        prompt.get("format_examples") or "—",
    ]
    web = prompt.get("web_context") or ""
    if web.strip():
        lines.extend(["", "## Интернет (если включён)", web])
    return "\n".join(lines)


def build_sources_zip_bytes(
    case_id: str,
    kpi_goal: str,
    *,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    raw_dir: Path | str = DEFAULT_RAW,
    use_web: bool = False,
) -> bytes:
    processed_dir = Path(processed_dir)
    raw_dir = Path(raw_dir)
    docs = list_case_source_documents(case_id, processed_dir=processed_dir, raw_dir=raw_dir)
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        readme = [
            f"Исходные и обработанные документы для кейса {case_id}.",
            f"KPI: {kpi_goal}",
            "",
            "Состав:",
            "- original/ — оригинальные файлы, если они лежат в data/raw/",
            "- processed/ — данные после ETL и контекст, который видит LLM",
            "",
            f"Если original/ пуст — скачайте датасет: {DATA_SOURCE_URL}",
        ]
        archive.writestr("README.txt", "\n".join(readme))

        for doc in docs:
            if doc.raw_path and doc.raw_path.exists():
                archive.write(doc.raw_path, arcname=f"original/{doc.name}")

        triplets_path = processed_dir / "cases" / case_id / "triplets.json"
        if triplets_path.exists():
            archive.write(triplets_path, arcname=f"processed/{case_id}_triplets.json")
        archive.writestr(
            f"processed/{case_id}_triplets.csv",
            triplets_to_csv_bytes(case_id, processed_dir=processed_dir),
        )

        literature_path = processed_dir / "literature" / "chunks.json"
        if literature_path.exists():
            archive.writestr(
                "processed/literature_excerpts.txt",
                chunks_to_text_bytes(literature_path, title="Литература (фрагменты PDF)"),
            )

        instructions_path = processed_dir / "instructions" / "chunks.json"
        if instructions_path.exists():
            archive.writestr(
                "processed/instructions_excerpts.txt",
                chunks_to_text_bytes(instructions_path, title="Инструкции"),
            )

        archive.writestr(
            f"processed/{case_id}_llm_context.md",
            build_llm_context_markdown(
                case_id,
                kpi_goal,
                processed_dir=processed_dir,
                use_web=use_web,
            ).encode("utf-8"),
        )

    return buffer.getvalue()
