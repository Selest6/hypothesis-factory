#!/usr/bin/env python3
"""Download organizer source files from public Yandex Disk into data/sources/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.source_downloads import list_required_source_files
from src.ui.yandex_disk import download_required_files

DEFAULT_OUT = ROOT / "data" / "sources"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    required = list_required_source_files()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = download_required_files(args.out_dir, required)
    present = sum(1 for n in required if (args.out_dir / n).exists())
    print(f"Downloaded: {downloaded} · present: {present}/{len(required)}")
    missing = [n for n in required if not (args.out_dir / n).exists()]
    if missing:
        print("Still missing:")
        for name in missing:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
