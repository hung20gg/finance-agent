#!/usr/bin/env python3
"""
Download a .zip dataset from Google Drive, extract to data_collection/data,
and remove macOS metadata (__MACOSX).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

import gdown
from dotenv import load_dotenv
from gdown.parse_url import parse_url

DATA_COLLECTION_DIR = Path(__file__).resolve().parent
FINANCE_AGENT_ROOT = DATA_COLLECTION_DIR.parent
DEFAULT_DATA_DIR = DATA_COLLECTION_DIR / "data"
MACOSX_DIR_NAMES = {"__MACOSX", "__MacOSX"}


def _load_env() -> None:
    load_dotenv(FINANCE_AGENT_ROOT / ".env")


def _remove_macosx(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.name in MACOSX_DIR_NAMES:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                print(f"Removed {path}")
            elif path.is_file():
                path.unlink(missing_ok=True)


def _resolve_payload_dir(extract_root: Path) -> Path:
    """Pick the folder that should become data_collection/data."""
    entries = [
        p
        for p in extract_root.iterdir()
        if p.name not in MACOSX_DIR_NAMES and not p.name.startswith(".")
    ]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extract_root


def download_zip(url: str, dest_zip: Path) -> None:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading from Google Drive...\n  URL: {url}\n  To:  {dest_zip}")

    file_id, _ = parse_url(url)
    if file_id:
        gdown.download(id=file_id, output=str(dest_zip), quiet=False)
    else:
        gdown.download(url=url, output=str(dest_zip), quiet=False)

    if not dest_zip.is_file() or dest_zip.stat().st_size == 0:
        raise RuntimeError(f"Download failed or empty file: {dest_zip}")

    # gdown sometimes saves an HTML warning page instead of the zip.
    with dest_zip.open("rb") as f:
        if f.read(2) != b"PK":
            raise RuntimeError(
                "Downloaded file is not a ZIP (Google Drive may require "
                "'Anyone with the link' access or the file is too large)."
            )


def extract_zip(zip_path: Path, extract_dir: Path) -> Path:
    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {zip_path.name} -> {extract_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    _remove_macosx(extract_dir)
    payload = _resolve_payload_dir(extract_dir)
    print(f"Payload directory: {payload}")
    return payload


def install_data(payload_dir: Path, target_dir: Path, *, replace: bool) -> None:
    if target_dir.exists():
        if not replace:
            raise FileExistsError(
                f"{target_dir} already exists. Use --replace or omit --no-replace."
            )
        print(f"Removing existing {target_dir}")
        shutil.rmtree(target_dir)

    if payload_dir.resolve() == target_dir.resolve():
        return

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(payload_dir), str(target_dir))
    print(f"Installed dataset at {target_dir}")


def _count_parquet(data_dir: Path) -> int:
    return sum(1 for _ in data_dir.rglob("*.parquet"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download parquet ZIP from Google Drive into data_collection/data."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("GDRIVE_ZIP_URL"),
        help="Google Drive file/share URL (or set GDRIVE_ZIP_URL in .env).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Final data folder (default: {DEFAULT_DATA_DIR}).",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep downloaded .zip and work directory after extraction.",
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Fail if output directory already exists.",
    )
    return parser.parse_args()


def main() -> int:
    _load_env()
    args = parse_args()
    if not args.url:
        print(
            "Missing Google Drive URL. Pass --url or set GDRIVE_ZIP_URL in .env",
            file=sys.stderr,
        )
        return 1

    work_dir = DATA_COLLECTION_DIR / "_gdown_work"
    zip_path = work_dir / "dataset.zip"
    extract_dir = work_dir / "extracted"
    target_dir = args.output_dir.resolve()
    replace = not args.no_replace

    try:
        if work_dir.exists():
            shutil.rmtree(work_dir)

        download_zip(args.url, zip_path)
        payload_dir = extract_zip(zip_path, extract_dir)
        install_data(payload_dir, target_dir, replace=replace)

        n_parquet = _count_parquet(target_dir)
        print(f"\nDone. {n_parquet} .parquet file(s) under {target_dir}")
        return 0 if n_parquet > 0 else 1
    finally:
        if not args.keep_zip and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
