#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_SOURCE_URL = "https://disk.yandex.ru/d/qE55fooRQGNVVA"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.etl.base import CASE_FOLDER_MAP, detect_case_from_path
from src.etl.docx_parser import parse_docx_hypotheses, parse_docx_text
from src.etl.excel_parser import parse_excel_tailings
from src.etl.pdf_parser import parse_pdf
from src.models.schemas import CaseIngestResult, IngestResult


def find_data_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    candidates = [
        ROOT / "data" / "raw",
        Path(r"C:\Users\alesi\Downloads\Задача 1\Задача 1"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(
        "Data directory not found. Pass --data-dir or copy dataset to data/raw/"
    )


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def manifest_data_root(data_root: Path) -> str:
    try:
        rel = data_root.resolve().relative_to(ROOT.resolve())
        return str(rel).replace("\\", "/")
    except ValueError:
        return "data/raw"


def ingest(data_root: Path, output_root: Path, copy_raw: bool = False) -> IngestResult:
    data_root = data_root.resolve()
    output_root = output_root.resolve()

    if copy_raw:
        raw_target = ROOT / "data" / "raw"
        if data_root.resolve() != raw_target.resolve():
            if raw_target.exists():
                shutil.rmtree(raw_target)
            shutil.copytree(data_root, raw_target)
            data_root = raw_target

    cases: dict[str, CaseIngestResult] = {}
    literature_chunks = []
    instruction_chunks = []

    for path in sorted(data_root.rglob("*")):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        case_info = detect_case_from_path(path)

        if suffix == ".xlsx" and "хвост" in path.name.lower():
            case_id = case_info[0] if case_info else path.parent.name
            case_name = case_info[1] if case_info else path.stem
            triplets = parse_excel_tailings(path, case_id=case_id)
            case = cases.setdefault(
                case_id,
                CaseIngestResult(case_id=case_id, case_name=case_name),
            )
            case.triplets.extend(triplets)
            continue

        if suffix == ".docx" and "гипотез" in path.name.lower():
            case_id = case_info[0] if case_info else path.parent.name
            case_name = case_info[1] if case_info else path.stem
            hyps, hyps_triplets = parse_docx_hypotheses(path, case_id=case_id)
            case = cases.setdefault(
                case_id,
                CaseIngestResult(case_id=case_id, case_name=case_name),
            )
            case.hypotheses.extend(hyps)
            case.triplets.extend(hyps_triplets)
            continue

        if suffix == ".docx":
            lower_name = path.name.lower()
            if "гипотез" not in lower_name:
                instruction_chunks.extend(parse_docx_text(path, chunk_type="instruction"))
            continue

        if suffix == ".pdf":
            literature_chunks.extend(parse_pdf(path))

    case_list = sorted(cases.values(), key=lambda item: item.case_id)
    result = IngestResult(
        cases=case_list,
        literature_chunks=literature_chunks,
        instruction_chunks=instruction_chunks,
        total_triplets=sum(len(case.triplets) for case in case_list),
        total_chunks=sum(len(case.chunks) for case in case_list)
        + len(literature_chunks)
        + len(instruction_chunks),
    )

    cases_dir = output_root / "cases"
    for case in case_list:
        case_dir = cases_dir / case.case_id
        save_json(case_dir / "triplets.json", [t.model_dump() for t in case.triplets])
        save_json(case_dir / "hypotheses.json", [h.model_dump() for h in case.hypotheses])
        save_json(
            case_dir / "meta.json",
            {
                "case_id": case.case_id,
                "case_name": case.case_name,
                "triplet_count": len(case.triplets),
                "hypothesis_count": len(case.hypotheses),
            },
        )

    save_json(
        output_root / "literature" / "chunks.json",
        [chunk.model_dump() for chunk in literature_chunks],
    )
    save_json(
        output_root / "instructions" / "chunks.json",
        [chunk.model_dump() for chunk in instruction_chunks],
    )
    save_json(
        output_root / "manifest.json",
        {
            "data_root": manifest_data_root(data_root),
            "data_source_url": DATA_SOURCE_URL,
            "cases": [
                {
                    "case_id": case.case_id,
                    "case_name": case.case_name,
                    "triplet_count": len(case.triplets),
                    "hypothesis_count": len(case.hypotheses),
                }
                for case in case_list
            ],
            "literature_chunk_count": len(literature_chunks),
            "instruction_chunk_count": len(instruction_chunks),
            "total_triplets": result.total_triplets,
            "total_chunks": result.total_chunks,
            "case_folder_map": CASE_FOLDER_MAP,
        },
    )
    save_json(
        output_root / "all_triplets.json",
        [t.model_dump() for case in case_list for t in case.triplets],
    )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest hackathon dataset into processed JSON.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to organizer dataset (default: data/raw or Downloads folder)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "processed",
        help="Directory for processed artifacts",
    )
    parser.add_argument(
        "--copy-raw",
        action="store_true",
        help="Copy source dataset into data/raw before processing",
    )
    args = parser.parse_args()

    data_root = find_data_root(args.data_dir)
    result = ingest(data_root, args.output_dir, copy_raw=args.copy_raw)

    print(f"Data root:      {data_root}")
    print(f"Output dir:     {args.output_dir.resolve()}")
    print(f"Cases:          {len(result.cases)}")
    for case in result.cases:
        print(
            f"  - {case.case_id}: {len(case.triplets)} triplets, "
            f"{len(case.hypotheses)} reference hypotheses"
        )
    print(f"Literature:     {len(result.literature_chunks)} chunks")
    print(f"Instructions:   {len(result.instruction_chunks)} chunks")
    print(f"Total triplets: {result.total_triplets}")


if __name__ == "__main__":
    main()
