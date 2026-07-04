from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.rag.context import retrieve_context

PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"


@dataclass
class KpiHotspot:
    subject: str
    element: str
    value: float
    unit: str
    context: str | None
    source_file: str
    source_sheet: str | None
    source_row: int | None


def _row_from_loss(row: dict[str, Any]) -> KpiHotspot | None:
    value = row.get("value")
    if value is None:
        return None
    src = row.get("source") or {}
    return KpiHotspot(
        subject=str(row.get("subject", "")),
        element=str(row.get("element", "")),
        value=float(value),
        unit=str(row.get("unit") or "т"),
        context=row.get("context"),
        source_file=str(src.get("file") or "—"),
        source_sheet=src.get("sheet"),
        source_row=src.get("row"),
    )


def hotspots_from_losses(top_losses: list[dict[str, Any]], *, top_n: int = 3) -> list[KpiHotspot]:
    hotspots: list[KpiHotspot] = []
    for row in top_losses:
        spot = _row_from_loss(row)
        if spot:
            hotspots.append(spot)
        if len(hotspots) >= top_n:
            break
    return hotspots


def diagnose_kpi(
    case_id: str,
    kpi_goal: str,
    *,
    top_n: int = 3,
    processed_dir: Path | str = PROCESSED,
) -> list[KpiHotspot]:
    ctx = retrieve_context(
        case_id,
        kpi_goal,
        processed_dir=processed_dir,
        use_chroma=False,
    )
    return hotspots_from_losses(ctx.top_losses, top_n=top_n)
