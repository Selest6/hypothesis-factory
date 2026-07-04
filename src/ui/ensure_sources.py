from __future__ import annotations

import subprocess
import sys
from pathlib import Path

DEFAULT_SOURCES = Path(__file__).resolve().parents[2] / "data" / "sources"
MARKER_FILE = "Хвосты КГМК.xlsx"


def sources_ready(sources_dir: Path = DEFAULT_SOURCES) -> bool:
    return (sources_dir / MARKER_FILE).is_file()


def download_sources_if_missing(*, sources_dir: Path = DEFAULT_SOURCES) -> bool:
    """Download organizer files from public Yandex Disk when data/sources is empty."""
    if sources_ready(sources_dir):
        return True

    script = Path(__file__).resolve().parents[2] / "scripts" / "download_yandex_disk_sources.py"
    if not script.exists():
        return False

    proc = subprocess.run(
        [sys.executable, str(script), "--out-dir", str(sources_dir)],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and sources_ready(sources_dir)
