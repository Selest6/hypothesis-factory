from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

import httpx

PUBLIC_KEY = "https://disk.yandex.ru/d/qE55fooRQGNVVA"
API = "https://cloud-api.yandex.net/v1/disk/public/resources"


def _list_dir(client: httpx.Client, path: str = "") -> list[dict]:
    params = {"public_key": PUBLIC_KEY, "limit": 200}
    if path:
        params["path"] = path
    resp = client.get(API, params=params, timeout=60)
    resp.raise_for_status()
    return (resp.json().get("_embedded") or {}).get("items") or []


def _walk_files(client: httpx.Client, path: str = "") -> list[dict]:
    found: list[dict] = []
    for item in _list_dir(client, path):
        item_path = item.get("path") or ""
        if item.get("type") == "dir":
            found.extend(_walk_files(client, item_path))
        elif item.get("type") == "file":
            found.append(item)
    return found


@lru_cache(maxsize=1)
def _filename_index() -> dict[str, str]:
    with httpx.Client() as client:
        files = _walk_files(client)
    return {
        str(item.get("name") or "").casefold(): str(item.get("path") or "")
        for item in files
        if item.get("name")
    }


def _download_disk_path(client: httpx.Client, disk_path: str, dest: Path) -> None:
    resp = client.get(
        f"{API}/download",
        params={"public_key": PUBLIC_KEY, "path": disk_path},
        timeout=60,
    )
    resp.raise_for_status()
    href = resp.json()["href"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with client.stream("GET", href, timeout=600, follow_redirects=True) as stream:
        stream.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in stream.iter_bytes():
                handle.write(chunk)


def fetch_file_from_public_disk(filename: str, dest_dir: Path) -> Path | None:
    """Download one original file by basename from organizer public folder."""
    filename = filename.strip()
    if not filename or filename.startswith("http"):
        return None

    dest = dest_dir / filename
    if dest.is_file() and dest.stat().st_size > 0:
        return dest

    disk_path = _filename_index().get(filename.casefold())
    if not disk_path:
        return None

    try:
        with httpx.Client() as client:
            _download_disk_path(client, disk_path, dest)
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
    except Exception:
        return None
    return None


def download_required_files(dest_dir: Path, required_names: list[str]) -> int:
    dest_dir.mkdir(parents=True, exist_ok=True)
    required = {name.casefold(): name.strip() for name in required_names if name.strip()}
    downloaded = 0

    with httpx.Client() as client:
        for item in _walk_files(client):
            name = str(item.get("name") or "")
            if not name or name.casefold() not in required:
                continue
            dest = dest_dir / name
            if dest.exists() and dest.stat().st_size == int(item.get("size") or 0):
                continue
            try:
                _download_disk_path(client, item.get("path") or "", dest)
                downloaded += 1
                time.sleep(0.2)
            except Exception:
                continue
    return downloaded
