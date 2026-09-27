"""Cross-layer contract check: dbt marts <-> Power BI semantic model.

For every model table loaded through fnLoadTable("<mart>"), verify that:
  * <mart> is a dbt mart with an enforced contract,
  * every column the M query names, and every TMDL sourceColumn, exists in that contract,
  * the TMDL dataType is compatible with the contract's data_type.

This catches the classic failure where someone renames a column in dbt and the Power BI refresh
breaks in production days later.

Usage:
    python scripts/check_model_contract.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARTS_YML = ROOT / "transform" / "models" / "marts" / "_marts__models.yml"
TABLES_DIR = ROOT / "powerbi" / "ContosoRetail.SemanticModel" / "definition" / "tables"

# dbt/DuckDB contract type -> TMDL dataType
TYPE_MAP = {
    "integer": "int64",
    "bigint": "int64",
    "date": "dateTime",
    "varchar": "string",
    "double": "double",
    "boolean": "boolean",
}


def contract_type(data_type: str) -> str:
    base = data_type.split("(")[0].strip().lower()
    return "decimal" if base == "decimal" else TYPE_MAP.get(base, f"?{base}")


def load_contracts() -> dict[str, dict[str, str]]:
    spec = yaml.safe_load(MARTS_YML.read_text(encoding="utf-8"))
    return {
        m["name"]: {c["name"]: c["data_type"] for c in m.get("columns", []) if "data_type" in c}
        for m in spec["models"]
    }


def parse_tmdl_table(text: str) -> tuple[str | None, list[tuple[str, str, str]], set[str]]:
    """Return (mart name, [(column name, sourceColumn, dataType)], columns named in M)."""
    mart = re.search(r'fnLoadTable\("([^"]+)"\)', text)
    columns = []
    for block in re.finditer(r"^\tcolumn (.+?)\n((?:\t\t.*\n|\n)+)", text, re.MULTILINE):
        body = block.group(2)
        source = re.search(r"^\t\tsourceColumn: (.+)$", body, re.MULTILINE)
        dtype = re.search(r"^\t\tdataType: (.+)$", body, re.MULTILINE)
        if source and dtype:
            columns.append((block.group(1).strip("'"), source.group(1).strip(), dtype.group(1).strip()))
    m_columns = set(re.findall(r'\{"([a-z0-9_]+)",\s*(?:Int64\.Type|Currency\.Type|type \w+)\}', text))
    m_columns |= {c for sel in re.findall(r"Table\.SelectColumns\(\w+, \{([^}]*)\}", text)
                  for c in re.findall(r'"([^"]+)"', sel)}
    return (mart.group(1) if mart else None), columns, m_columns


def main() -> int:
    contracts = load_contracts()
    problems: list[str] = []
    checked = 0

    for path in sorted(TABLES_DIR.glob("*.tmdl")):
        mart, columns, m_columns = parse_tmdl_table(path.read_text(encoding="utf-8"))
        if mart is None:
            continue  # measures table, calculation group, field parameter
        checked += 1
        if mart not in contracts:
            problems.append(f"{path.name}: fnLoadTable(\"{mart}\") is not a dbt mart with a contract")
            continue
        contract = contracts[mart]
        for col in sorted(m_columns - contract.keys()):
            problems.append(f"{path.name}: M query uses '{col}', which is not in the {mart} contract")
        for name, source, dtype in columns:
            if source not in contract:
                problems.append(f"{path.name}: column '{name}' reads '{source}', not in the {mart} contract")
                continue
            expected = contract_type(contract[source])
            if expected != dtype:
                problems.append(
                    f"{path.name}: column '{name}' is {dtype} but {mart}.{source} is {contract[source]} (expected {expected})"
                )
        unmapped = contract.keys() - {s for _, s, _ in columns}
        if unmapped:
            print(f"  note: {mart} columns not loaded into the model: {', '.join(sorted(unmapped))}")

    for p in problems:
        print(f"ERROR {p}")
    print(f"Checked {checked} model tables against {len(contracts)} dbt contracts: "
          f"{'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
