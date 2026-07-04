#!/usr/bin/env python3
"""Copy original source files referenced by the pipeline into data/sources/."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.source_downloads import list_required_source_files, resolve_original_file

DEFAULT_OUT = ROOT / "data" / "sources"
DEFAULT_RAW = ROOT / "data" / "raw"


def find_in_tree(name: str, root: Path) -> Path | None:
    target = name.casefold()
    for path in root.rglob("*"):
        if path.is_file() and path.name.casefold() == target:
            return path
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_RAW,
        help="Dataset root (default: data/raw)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT,
        help="Output directory for flat originals (default: data/sources)",
    )
    args = parser.parse_args()

    required = list_required_source_files()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    missing: list[str] = []

    for name in required:
        src = resolve_original_file(name, sources_dir=args.out_dir, raw_dir=args.data_dir)
        if src and src.parent.resolve() == args.out_dir.resolve():
            continue
        found = find_in_tree(name, args.data_dir)
        if not found:
            missing.append(name)
            continue
        dest = args.out_dir / name
        shutil.copy2(found, dest)
        copied += 1
        print(f"copied: {name}")

    print(f"\nRequired: {len(required)} · copied: {copied} · missing: {len(missing)}")
    if missing:
        print("Missing files:")
        for name in missing:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
