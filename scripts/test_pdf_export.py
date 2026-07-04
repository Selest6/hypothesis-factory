#!/usr/bin/env python3
"""Compare PDF export variants."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from src.llm.pipeline import run_pipeline
from src.ui.export import FONT_PATH, result_to_pdf_bytes


def main() -> None:
    result = run_pipeline("kgmk", mode="demo")
    pdf = result_to_pdf_bytes(result, "Без капитальных затрат")
    out = ROOT / "data" / "test_export_current.pdf"
    out.write_bytes(pdf)
    print(f"font exists: {FONT_PATH.exists()} ({FONT_PATH})")
    print(f"wrote {out} ({len(pdf)} bytes)")


if __name__ == "__main__":
    main()
