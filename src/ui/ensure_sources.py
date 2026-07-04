from __future__ import annotations

from pathlib import Path

from src.ui.source_downloads import list_required_source_files
from src.ui.yandex_disk import download_required_files

DEFAULT_SOURCES = Path(__file__).resolve().parents[2] / "data" / "sources"
MARKER_FILE = "Хвосты КГМК.xlsx"


def sources_ready(sources_dir: Path = DEFAULT_SOURCES) -> bool:
    return (sources_dir / MARKER_FILE).is_file()


def download_sources_if_missing(*, sources_dir: Path = DEFAULT_SOURCES) -> bool:
    """Download organizer files from public Yandex Disk when data/sources is empty."""
    if sources_ready(sources_dir):
        return True
    required = list_required_source_files()
    download_required_files(sources_dir, required)
    return sources_ready(sources_dir)
