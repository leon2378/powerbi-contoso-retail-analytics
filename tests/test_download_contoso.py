import py7zr
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import download_contoso as dc


def make_archive(folder, file_names):
    """A .7z like SQLBI's release: Parquet files inside a subfolder."""
    source = folder / "source"
    source.mkdir()
    for name in file_names:
        pq.write_table(pa.table({"key": [1, 2, 3]}), source / name)
    archive = folder / "parquet-test.7z"
    with py7zr.SevenZipFile(archive, "w") as z:
        for path in source.iterdir():
            z.write(path, f"data/{path.name}")
    return archive


def test_stage_replaces_raw_with_lower_case_tables(tmp_path, capsys):
    archive = make_archive(tmp_path, ["sales.parquet", "customer.parquet", "product.parquet", "Store.parquet"])
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "stale.parquet").write_bytes(b"old")

    dc.stage(archive, raw)

    assert sorted(p.name for p in raw.iterdir()) == [
        "customer.parquet", "product.parquet", "sales.parquet", "store.parquet"]
    assert "3 rows" in capsys.readouterr().out


def test_stage_keeps_the_current_data_when_a_table_is_missing(tmp_path):
    archive = make_archive(tmp_path, ["sales.parquet", "customer.parquet", "product.parquet"])
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sales.parquet").write_bytes(b"current data")

    with pytest.raises(SystemExit, match="store"):
        dc.stage(archive, raw)
    assert (raw / "sales.parquet").read_bytes() == b"current data"
