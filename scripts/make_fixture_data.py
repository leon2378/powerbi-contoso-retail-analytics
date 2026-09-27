"""Generate a small, deterministic dataset with the exact schema of the SQLBI Contoso V2
Parquet release.

CI uses it so `dbt build` runs in seconds without downloading hundreds of MB, and so tests
are reproducible. Column names and physical types (timestamp[ms], decimal(20,5), int32/int64)
mirror the generator's ParquetWriter classes, so a schema drift in the models fails here too.

Usage:
    python scripts/make_fixture_data.py [--out data/raw] [--orders 2500] [--seed 42]
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

MONEY = pa.decimal128(20, 5)
TS = pa.timestamp("ms")

COUNTRIES = {
    # code: (country name, continent, currency, usd->local rate, states)
    "US": ("United States", "North America", "USD", Decimal("1"), [("WA", "Washington"), ("NY", "New York")]),
    "DE": ("Germany", "Europe", "EUR", Decimal("0.91"), [("BY", "Bavaria"), ("BE", "Berlin")]),
    "GB": ("United Kingdom", "Europe", "GBP", Decimal("0.79"), [("ENG", "England"), ("SCT", "Scotland")]),
    "CA": ("Canada", "North America", "CAD", Decimal("1.36"), [("ON", "Ontario"), ("BC", "British Columbia")]),
}

CATEGORIES = [
    (1, "Audio", [(101, "MP4&MP3"), (102, "Recording Pen")]),
    (3, "Computers", [(301, "Laptops"), (302, "Monitors")]),
    (5, "Cell phones", [(501, "Smart phones & PDAs"), (502, "Touch Screen Phones")]),
    (8, "Home Appliances", [(801, "Washers & Dryers"), (802, "Microwaves")]),
]
BRANDS = ["Contoso", "Fabrikam", "Litware", "Proseware", "Adventure Works"]
COLORS = ["Black", "White", "Silver", "Blue", "Red"]


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)


def ts(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def build(orders: int, seed: int) -> dict[str, pa.Table]:
    rng = random.Random(seed)

    # --- products -------------------------------------------------------------------------
    products = []
    key = 1
    for cat_key, cat_name, subcats in CATEGORIES:
        for sub_key, sub_name in subcats:
            for i in range(5):
                cost = rng.uniform(15, 900)
                price = cost * rng.uniform(1.6, 2.2)
                brand = rng.choice(BRANDS)
                products.append(
                    dict(
                        ProductKey=key,
                        ProductCode=f"{sub_key:04d}{i:03d}",
                        ProductName=f"{brand} {sub_name} {chr(65 + i)}{key:03d}",
                        Manufacturer=f"{brand}, Ltd",
                        Brand=brand,
                        Color=rng.choice(COLORS),
                        WeightUnit="pounds",
                        Weight=money(rng.uniform(0.2, 40)),
                        Cost=money(cost),
                        Price=money(price),
                        CategoryKey=cat_key,
                        CategoryName=cat_name,
                        SubCategoryKey=sub_key,
                        SubCategoryName=sub_name,
                    )
                )
                key += 1

    # --- stores (plus the generator's single online store: GeoAreaKey = -1) --------------
    stores = []
    store_key = 1
    for code, (name, _, _, _, states) in COUNTRIES.items():
        for state_code, state_name in states:
            stores.append(
                dict(
                    StoreKey=store_key,
                    StoreCode=store_key,
                    GeoAreaKey=100 + store_key,
                    CountryCode=code,
                    CountryName=name,
                    State=state_name,
                    OpenDate=ts(date(2015 + store_key % 5, 1 + store_key % 12, 1)),
                    CloseDate=ts(date(2024, 3, 31)) if store_key == 4 else None,
                    Description=f"Contoso Store {state_name}",
                    SquareMeters=rng.choice([500, 900, 1300, 2000]),
                    Status="Closed" if store_key == 4 else "",
                )
            )
            store_key += 1
    # Mirrors the real release: StoreKey 999999, StoreCode -1, CountryCode '--', Status null.
    stores.append(
        dict(
            StoreKey=999999, StoreCode=-1, GeoAreaKey=-1, CountryCode="--", CountryName="Online",
            State="Online", OpenDate=ts(date(2010, 1, 1)), CloseDate=None, Description="Contoso Online Store",
            SquareMeters=None, Status=None,
        )
    )

    # --- customers ------------------------------------------------------------------------
    customers = []
    for ckey in range(1, 301):
        code = rng.choice(list(COUNTRIES))
        cname, continent, _, _, states = COUNTRIES[code]
        state_code, state_name = rng.choice(states)
        birthday = date(1950, 1, 1) + timedelta(days=rng.randint(0, 365 * 55))
        customers.append(
            dict(
                CustomerKey=ckey, GeoAreaKey=500 + ckey % 7, StartDT=None, EndDT=None, Continent=continent,
                Gender=rng.choice(["male", "female"]), Title=rng.choice(["Mr.", "Ms.", "Mrs."]),
                GivenName=f"Given{ckey}", MiddleInitial="A", Surname=f"Surname{ckey}",
                StreetAddress=f"{ckey} Fixture Street", City=f"City {ckey % 9}", State=state_code,
                StateFull=state_name, ZipCode=f"{10000 + ckey}", Country=code, CountryFull=cname,
                Birthday=ts(birthday), Age=2024 - birthday.year, Occupation="Professional",
                Company="Fixture Corp", Vehicle="Bicycle", Latitude=money(rng.uniform(-40, 60)),
                Longitude=money(rng.uniform(-120, 30)),
            )
        )

    # --- sales (order lines) ----------------------------------------------------------------
    start, end = date(2022, 1, 1), date(2024, 6, 30)
    span = (end - start).days
    physical_by_country: dict[str, list[dict]] = {}
    for s in stores:
        if s["GeoAreaKey"] != -1 and s["CloseDate"] is None:
            physical_by_country.setdefault(s["CountryCode"], []).append(s)

    sales = []
    for order_key in range(1, orders + 1):
        order_date = start + timedelta(days=rng.randint(0, span))
        customer = rng.choice(customers)
        online = rng.random() < 0.2 or customer["Country"] not in physical_by_country
        store = stores[-1] if online else rng.choice(physical_by_country[customer["Country"]])
        _, _, currency, rate, _ = COUNTRIES[customer["Country"]]
        delivery = order_date + timedelta(days=rng.randint(1, 7) if online else 0)
        for line in range(rng.randint(1, 4)):
            product = rng.choice(products)
            discount = rng.choice([0, 0, 0, 0.05, 0.10, 0.15])
            sales.append(
                dict(
                    OrderKey=order_key, LineNumber=line, OrderDate=ts(order_date),
                    DeliveryDate=ts(delivery), CustomerKey=customer["CustomerKey"], StoreKey=store["StoreKey"],
                    ProductKey=product["ProductKey"], Quantity=rng.randint(1, 5), UnitPrice=product["Price"],
                    NetPrice=money(product["Price"] * Decimal(str(1 - discount))), UnitCost=product["Cost"],
                    CurrencyCode=currency, ExchangeRate=money(rate),
                )
            )

    schemas = {
        "product": pa.schema([
            ("ProductKey", pa.int32()), ("ProductCode", pa.string()), ("ProductName", pa.string()),
            ("Manufacturer", pa.string()), ("Brand", pa.string()), ("Color", pa.string()),
            ("WeightUnit", pa.string()), ("Weight", MONEY), ("Cost", MONEY), ("Price", MONEY),
            ("CategoryKey", pa.int32()), ("CategoryName", pa.string()), ("SubCategoryKey", pa.int32()),
            ("SubCategoryName", pa.string()),
        ]),
        "store": pa.schema([
            ("StoreKey", pa.int32()), ("StoreCode", pa.int32()), ("GeoAreaKey", pa.int32()),
            ("CountryCode", pa.string()), ("CountryName", pa.string()), ("State", pa.string()),
            ("OpenDate", TS), ("CloseDate", TS), ("Description", pa.string()),
            ("SquareMeters", pa.int32()), ("Status", pa.string()),
        ]),
        "customer": pa.schema([
            ("CustomerKey", pa.int32()), ("GeoAreaKey", pa.int32()), ("StartDT", TS), ("EndDT", TS),
            ("Continent", pa.string()), ("Gender", pa.string()), ("Title", pa.string()),
            ("GivenName", pa.string()), ("MiddleInitial", pa.string()), ("Surname", pa.string()),
            ("StreetAddress", pa.string()), ("City", pa.string()), ("State", pa.string()),
            ("StateFull", pa.string()), ("ZipCode", pa.string()), ("Country", pa.string()),
            ("CountryFull", pa.string()), ("Birthday", TS), ("Age", pa.int32()),
            ("Occupation", pa.string()), ("Company", pa.string()), ("Vehicle", pa.string()),
            ("Latitude", MONEY), ("Longitude", MONEY),
        ]),
        "sales": pa.schema([
            ("OrderKey", pa.int64()), ("LineNumber", pa.int32()), ("OrderDate", TS), ("DeliveryDate", TS),
            ("CustomerKey", pa.int32()), ("StoreKey", pa.int32()), ("ProductKey", pa.int32()),
            ("Quantity", pa.int32()), ("UnitPrice", MONEY), ("NetPrice", MONEY), ("UnitCost", MONEY),
            ("CurrencyCode", pa.string()), ("ExchangeRate", MONEY),
        ]),
    }
    rows = {"product": products, "store": stores, "customer": customers, "sales": sales}
    return {name: pa.Table.from_pylist(rows[name], schema=schema) for name, schema in schemas.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="data/raw", type=Path)
    parser.add_argument("--orders", default=2500, type=int)
    parser.add_argument("--seed", default=42, type=int)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for name, table in build(args.orders, args.seed).items():
        pq.write_table(table, args.out / f"{name}.parquet")
        print(f"wrote {args.out / f'{name}.parquet'}  ({table.num_rows:,} rows)")


if __name__ == "__main__":
    main()
