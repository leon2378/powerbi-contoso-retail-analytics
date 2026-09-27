"""Download a ready-to-use Contoso V2 Parquet release from SQLBI and stage it in data/raw.

Source: https://github.com/sql-bi/Contoso-Data-Generator-V2-Data/releases (tag: ready-to-use-data)

    size    orders   archive      Sales rows (order lines)
    100k    100 K    ~10 MB       ~0.2 M
    1m      1 M      ~66 MB       ~2.2 M
    10m     10 M     ~680 MB      ~22 M

The 100m release is split across multiple volumes and is intentionally not supported here: at
that scale use Direct Lake on a Fabric Lakehouse instead of importing into the model.

Usage:
    python scripts/download_contoso.py --size 100k
    python scripts/download_contoso.py --size 1m --force
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import py7zr
import pyarrow.parquet as pq
import requests

RELEASE_URL = "https://github.com/sql-bi/Contoso-Data-Generator-V2-Data/releases/download/ready-to-use-data"
SIZES = ("100k", "1m", "10m")
REQUIRED_TABLES = ("sales", "customer", "product", "store")


def download(url: str, target: Path) -> None:
    tmp = target.with_suffix(target.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done / 1e6:,.1f} / {total / 1e6:,.1f} MB", end="", flush=True)
    print()
    tmp.replace(target)


def stage(archive: Path, raw_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with py7zr.SevenZipFile(archive, mode="r") as z:
            z.extractall(path=tmp)
        files = list(Path(tmp).rglob("*.parquet"))
        if not files:
            sys.exit(f"No .parquet files found in {archive.name}")
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
        raw_dir.mkdir(parents=True)
        for f in files:
            # Normalise names: the generator writes lower-case table names; be defensive anyway.
            shutil.move(str(f), raw_dir / f.name.lower())

    missing = [t for t in REQUIRED_TABLES if not (raw_dir / f"{t}.parquet").exists()]
    if missing:
        sys.exit(f"Archive is missing required tables: {missing}")
    for f in sorted(raw_dir.glob("*.parquet")):
        print(f"  {f.name:<24} {pq.ParquetFile(f).metadata.num_rows:>14,} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", choices=SIZES, default="100k")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/downloads"))
    parser.add_argument("--force", action="store_true", help="re-download even if the archive is cached")
    args = parser.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    archive = args.cache_dir / f"parquet-{args.size}.7z"
    if archive.exists() and not args.force:
        print(f"Using cached {archive}")
    else:
        url = f"{RELEASE_URL}/{archive.name}"
        print(f"Downloading {url}")
        download(url, archive)

    print(f"Extracting into {args.raw_dir}")
    stage(archive, args.raw_dir)


if __name__ == "__main__":
    main()
