"""Publish the dbt marts (data/marts/*.parquet) to a Fabric Lakehouse as Delta tables.

Each mart overwrites its Delta table in one transaction, so the SQL analytics endpoint and any
Direct Lake model always see a complete version. Data is streamed in record batches, so the
10M-order dataset does not need to fit in memory.

Usage:
    python scripts/publish_to_onelake.py --workspace-id <guid> [--lakehouse lh_contoso]
Environment variables FABRIC_WORKSPACE_ID / FABRIC_LAKEHOUSE_NAME can replace the flags.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from deltalake import write_deltalake

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fabric_common import STORAGE_SCOPE, FabricClient, Lakehouse  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def publish(client: FabricClient, lakehouse: Lakehouse, marts_dir: Path, tables: list[str] | None = None) -> None:
    files = sorted(marts_dir.glob("*.parquet"))
    if tables:
        files = [f for f in files if f.stem in tables]
    if not files:
        sys.exit(f"No marts found in {marts_dir}. Run the dbt build first.")

    token = client.credential.get_token(STORAGE_SCOPE).token
    storage_options = {"bearer_token": token, "use_fabric_endpoint": "true"}
    for f in files:
        source = pq.ParquetFile(f)
        reader = pa.RecordBatchReader.from_batches(source.schema_arrow, source.iter_batches(batch_size=250_000))
        uri = f"{lakehouse.tables_uri}/{f.stem}"
        write_deltalake(uri, reader, mode="overwrite", schema_mode="overwrite", storage_options=storage_options)
        print(f"  {f.stem:<24} {source.metadata.num_rows:>12,} rows -> {lakehouse.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace-id", default=os.environ.get("FABRIC_WORKSPACE_ID"))
    parser.add_argument("--lakehouse", default=os.environ.get("FABRIC_LAKEHOUSE_NAME", "lh_contoso"))
    parser.add_argument("--marts-dir", type=Path, default=ROOT / "data" / "marts")
    parser.add_argument("--tables", nargs="*", help="subset of marts to publish (default: all)")
    args = parser.parse_args()
    if not args.workspace_id:
        sys.exit("--workspace-id (or FABRIC_WORKSPACE_ID) is required")

    client = FabricClient()
    lakehouse = client.ensure_lakehouse(args.workspace_id, args.lakehouse)
    print(f"Publishing marts to {lakehouse.name} ({lakehouse.tables_uri})")
    publish(client, lakehouse, args.marts_dir, args.tables)
    client.refresh_sql_endpoint_metadata(lakehouse)


if __name__ == "__main__":
    main()
