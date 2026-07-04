#!/usr/bin/env python3
"""Download organizer source files from public Yandex Disk into data/sources/."""
from __future__ import annotations

import argparse
import sys
import time
import urllib.parse
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui.source_downloads import list_required_source_files

PUBLIC_KEY = "https://disk.yandex.ru/d/qE55fooRQGNVVA"
API = "https://cloud-api.yandex.net/v1/disk/public/resources"
DEFAULT_OUT = ROOT / "data" / "sources"


def list_dir(client: httpx.Client, path: str = "") -> list[dict]:
    params = {"public_key": PUBLIC_KEY, "limit": 200}
    if path:
        params["path"] = path
    resp = client.get(API, params=params, timeout=60)
    resp.raise_for_status()
    embedded = resp.json().get("_embedded") or {}
    return embedded.get("items") or []


def walk_files(client: httpx.Client, path: str = "") -> list[dict]:
    found: list[dict] = []
    for item in list_dir(client, path):
        item_path = item.get("path") or ""
        if item.get("type") == "dir":
            found.extend(walk_files(client, item_path))
        elif item.get("type") == "file":
            found.append(item)
    return found


def download_file(client: httpx.Client, disk_path: str, dest: Path) -> None:
    resp = client.get(
        f"{API}/download",
        params={"public_key": PUBLIC_KEY, "path": disk_path},
        timeout=60,
    )
    resp.raise_for_status()
    href = resp.json()["href"]
    with client.stream("GET", href, timeout=300, follow_redirects=True) as stream:
        stream.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            for chunk in stream.iter_bytes():
                handle.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all files from disk (default: only files referenced by pipeline)",
    )
    args = parser.parse_args()

    required = {name.casefold(): name for name in list_required_source_files()}
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        files = walk_files(client)
        print(f"Found {len(files)} files on Yandex Disk")

        downloaded = 0
        skipped = 0
        for item in files:
            name = str(item.get("name") or "")
            if not name or "гипотез" in name.lower():
                continue
            if not args.all and name.casefold() not in required:
                skipped += 1
                continue

            dest = args.out_dir / name
            if dest.exists() and dest.stat().st_size == int(item.get("size") or 0):
                print(f"skip (exists): {name}")
                continue

            disk_path = item.get("path") or ""
            print(f"download: {name}")
            try:
                download_file(client, disk_path, dest)
                downloaded += 1
                time.sleep(0.3)
            except Exception as exc:
                print(f"  failed: {exc}")

    print(f"\nDownloaded: {downloaded} · skipped (not required): {skipped}")
    present = sum(1 for n in required.values() if (args.out_dir / n).exists())
    print(f"Required present: {present}/{len(required)}")
    missing = [n for n in required.values() if not (args.out_dir / n).exists()]
    if missing:
        print("Still missing:")
        for name in missing:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
