from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.etl.base import (
    detect_case_from_path,
    is_mineral_row,
    is_size_class_header,
    normalize_label,
    safe_float,
)
from src.models.schemas import NodeType, SourceRef, Triplet


def _make_triplet(
    *,
    subject: str,
    subject_type: NodeType,
    predicate: str,
    obj: str,
    object_type: NodeType,
    source: SourceRef,
    case_id: str,
    metadata: dict | None = None,
) -> Triplet:
    return Triplet(
        subject=subject,
        subject_type=subject_type,
        predicate=predicate,
        object=obj,
        object_type=object_type,
        source=source,
        case_id=case_id,
        metadata=metadata or {},
    )


def _metric_triplets(
    entity: str,
    entity_type: NodeType,
    row_idx: int,
    el28_pct,
    el28_t,
    el29_pct,
    el29_t,
    source: SourceRef,
    case_id: str,
    context: str,
) -> list[Triplet]:
    triplets: list[Triplet] = []
    metrics = [
        ("Элемент 28", el28_pct, "%", "loss_percent"),
        ("Элемент 28", el28_t, "т", "loss_tons"),
        ("Элемент 29", el29_pct, "%", "loss_percent"),
        ("Элемент 29", el29_t, "т", "loss_tons"),
    ]
    for element, raw_value, unit, metric_kind in metrics:
        value = safe_float(raw_value)
        if value is None:
            continue
        triplets.append(
            _make_triplet(
                subject=entity,
                subject_type=entity_type,
                predicate="loses_to",
                obj=f"{element}: {value} {unit}",
                object_type=NodeType.METRIC,
                source=source.model_copy(update={"row": row_idx}),
                case_id=case_id,
                metadata={
                    "element": element,
                    "value": value,
                    "unit": unit,
                    "metric_kind": metric_kind,
                    "context": context,
                },
            )
        )
    return triplets


def parse_excel_tailings(path: Path, case_id: str | None = None) -> list[Triplet]:
    """Parse a tailings Excel report into knowledge-graph triplets."""
    path = Path(path)
    case = detect_case_from_path(path)
    if case_id is None:
        if case is None:
            case_id = path.stem.lower().replace(" ", "_")
        else:
            case_id = case[0]

    plant_name = case[1] if case else path.stem
    triplets: list[Triplet] = []

    xl = pd.ExcelFile(path)
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet_name, header=None)
        source = SourceRef(file=path.name, sheet=sheet_name)

        triplets.append(
            _make_triplet(
                subject=plant_name,
                subject_type=NodeType.PLANT,
                predicate="has_source",
                obj=path.name,
                object_type=NodeType.SOURCE,
                source=source,
                case_id=case_id,
            )
        )

        current_size_class: str | None = None
        in_tailings = False

        for row_idx, row in df.iterrows():
            label_raw = row.iloc[1] if len(row) > 1 else None
            if pd.isna(label_raw):
                continue

            label = normalize_label(str(label_raw))
            label_lower = label.lower()
            row_source = source.model_copy(update={"row": int(row_idx) + 1, "fragment": label})

            if label_lower == "поступило в переработку":
                in_tailings = False
                current_size_class = None
                continue

            if label_lower == "отвальные хвосты":
                in_tailings = True
                current_size_class = "Отвальные хвосты"
                mass = safe_float(row.iloc[2]) if len(row) > 2 else None
                if mass is not None:
                    triplets.append(
                        _make_triplet(
                            subject=plant_name,
                            subject_type=NodeType.PLANT,
                            predicate="has_material",
                            obj="Отвальные хвосты",
                            object_type=NodeType.MATERIAL,
                            source=row_source,
                            case_id=case_id,
                            metadata={"mass_smt": mass},
                        )
                    )
                    triplets.append(
                        _make_triplet(
                            subject="Отвальные хвосты",
                            subject_type=NodeType.MATERIAL,
                            predicate="has_mass",
                            obj=f"{mass} т",
                            object_type=NodeType.METRIC,
                            source=row_source,
                            case_id=case_id,
                        )
                    )
                triplets.extend(
                    _metric_triplets(
                        "Отвальные хвосты",
                        NodeType.MATERIAL,
                        int(row_idx) + 1,
                        row.iloc[3] if len(row) > 3 else None,
                        row.iloc[4] if len(row) > 4 else None,
                        row.iloc[5] if len(row) > 5 else None,
                        row.iloc[6] if len(row) > 6 else None,
                        source,
                        case_id,
                        "tailings_summary",
                    )
                )
                continue

            if is_size_class_header(label):
                current_size_class = label
                triplets.append(
                    _make_triplet(
                        subject="Отвальные хвосты",
                        subject_type=NodeType.MATERIAL,
                        predicate="has_size_class",
                        obj=current_size_class,
                        object_type=NodeType.SIZE_CLASS,
                        source=row_source,
                        case_id=case_id,
                    )
                )
                continue

            if in_tailings and is_mineral_row(label):
                mineral = label
                triplets.append(
                    _make_triplet(
                        subject=mineral,
                        subject_type=NodeType.MINERAL,
                        predicate="found_in",
                        obj=current_size_class or "Отвальные хвосты",
                        object_type=NodeType.SIZE_CLASS if current_size_class else NodeType.MATERIAL,
                        source=row_source,
                        case_id=case_id,
                    )
                )
                triplets.extend(
                    _metric_triplets(
                        mineral,
                        NodeType.MINERAL,
                        int(row_idx) + 1,
                        row.iloc[3] if len(row) > 3 else None,
                        row.iloc[4] if len(row) > 4 else None,
                        row.iloc[5] if len(row) > 5 else None,
                        row.iloc[6] if len(row) > 6 else None,
                        source,
                        case_id,
                        current_size_class or "tailings",
                    )
                )
                for element, pct_col, t_col in [
                    ("Элемент 28", 3, 4),
                    ("Элемент 29", 5, 6),
                ]:
                    pct = safe_float(row.iloc[pct_col] if len(row) > pct_col else None)
                    tons = safe_float(row.iloc[t_col] if len(row) > t_col else None)
                    if pct is not None and pct > 0:
                        triplets.append(
                            _make_triplet(
                                subject=mineral,
                                subject_type=NodeType.MINERAL,
                                predicate="potentially_extractable",
                                obj=element,
                                object_type=NodeType.ELEMENT,
                                source=row_source,
                                case_id=case_id,
                                metadata={"share_percent": pct, "tons": tons},
                            )
                        )
                continue

            if label_lower in {"итого", "итого (проверка)"}:
                continue

            if not in_tailings and label_lower not in {"материал", "смт"}:
                mass = safe_float(row.iloc[2]) if len(row) > 2 else None
                triplets.append(
                    _make_triplet(
                        subject=plant_name,
                        subject_type=NodeType.PLANT,
                        predicate="has_feed_material",
                        obj=label,
                        object_type=NodeType.MATERIAL,
                        source=row_source,
                        case_id=case_id,
                        metadata={"mass_smt": mass} if mass is not None else {},
                    )
                )
                if mass is not None:
                    triplets.append(
                        _make_triplet(
                            subject=label,
                            subject_type=NodeType.MATERIAL,
                            predicate="has_mass",
                            obj=f"{mass} т",
                            object_type=NodeType.METRIC,
                            source=row_source,
                            case_id=case_id,
                        )
                    )
                triplets.extend(
                    _metric_triplets(
                        label,
                        NodeType.MATERIAL,
                        int(row_idx) + 1,
                        row.iloc[3] if len(row) > 3 else None,
                        row.iloc[4] if len(row) > 4 else None,
                        row.iloc[5] if len(row) > 5 else None,
                        row.iloc[6] if len(row) > 6 else None,
                        source,
                        case_id,
                        "feed",
                    )
                )

    return triplets
