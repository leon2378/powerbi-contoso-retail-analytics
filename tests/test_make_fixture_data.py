import csv
from collections import Counter

import pyarrow as pa

import make_fixture_data as mfd
from conftest import ROOT


def test_same_seed_gives_identical_data():
    first, second = mfd.build(300, seed=7), mfd.build(300, seed=7)
    assert all(first[name].equals(second[name]) for name in first)


def test_physical_types_match_the_sqlbi_release():
    sales = mfd.build(50, seed=1)["sales"].schema
    assert sales.field("OrderKey").type == pa.int64()
    assert sales.field("OrderDate").type == pa.timestamp("ms")
    assert sales.field("NetPrice").type == pa.decimal128(20, 5)


def test_every_rls_country_has_a_store():
    """Otherwise the security_user_access relationship test warns on every CI run."""
    with open(ROOT / "transform" / "seeds" / "rls_user_access.csv", encoding="utf-8") as fh:
        entitled = {row["country_code"] for row in csv.DictReader(fh)} - {"ONLINE"}
    stores = set(mfd.build(10, seed=1)["store"].column("CountryCode").to_pylist())
    assert entitled <= stores


def test_every_order_has_exactly_one_first_line():
    """The [Orders] measure counts line-0 rows; the fixtures must keep that assumption true."""
    sales = mfd.build(500, seed=3)["sales"]
    first_lines = Counter(
        order for order, line in zip(sales.column("OrderKey").to_pylist(), sales.column("LineNumber").to_pylist())
        if line == 0
    )
    orders = set(sales.column("OrderKey").to_pylist())
    assert set(first_lines) == orders and set(first_lines.values()) == {1}
