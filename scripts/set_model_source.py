"""Switch the semantic model's data source between local Parquet files and a Fabric Lakehouse.

Every table partition loads through the shared M function fnLoadTable (expressions.tmdl). This
script rewrites only that function's body and the related parameters, so the switch is one
explicit, reviewable diff instead of edits across every table.

Why not an `if Mode = "Local" then ... else ...` inside M? The Power BI service inspects every data
source referenced in a query. A File.Contents branch, even an unused one, would make the model
require an on-premises gateway, so each mode has to contain only its own source.

Usage:
    python scripts/set_model_source.py local                 # DataRoot := <repo>/data/marts
    python scripts/set_model_source.py local --data-root D:/contoso/marts
    python scripts/set_model_source.py fabric --sql-endpoint abc.datawarehouse.fabric.microsoft.com --lakehouse lh_contoso
    python scripts/set_model_source.py status
    python scripts/set_model_source.py reset                 # local mode + placeholder path (clean for commits)

--definition points at another copy of the model (scripts/deploy_fabric.py uses it on its build copy).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEFINITION = ROOT / "powerbi" / "ContosoRetail.SemanticModel" / "definition"
PLACEHOLDER_DATA_ROOT = r"C:\path\to\contoso-retail-analytics\data\marts"
PLACEHOLDER_SQL_ENDPOINT = "your-endpoint.datawarehouse.fabric.microsoft.com"
UNUSED = "(not used in this source mode)"

TEMPLATES = {
    "local": [
        "// source-mode: local",
        "(tableName as text) as table =>",
        "let",
        '    Folder = Text.TrimEnd(DataRoot, {"\\", "/"}),',
        '    Source = Parquet.Document(File.Contents(Folder & "\\" & tableName & ".parquet"))',
        "in",
        "    Source",
    ],
    "fabric": [
        "// source-mode: fabric",
        "(tableName as text) as table =>",
        "let",
        "    Source = Sql.Database(SqlEndpoint, LakehouseName),",
        '    Data = Source{[Schema = "dbo", Item = tableName]}[Data]',
        "in",
        "    Data",
    ],
}


def read(path: Path) -> tuple[list[str], str]:
    raw = path.read_bytes().decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n").split("\n"), newline


def current_mode(lines: list[str]) -> str:
    for line in lines:
        m = re.match(r"^\t\t// source-mode: (\w+)", line)
        if m:
            return m.group(1)
    return "unknown"


def set_parameter(lines: list[str], name: str, value: str) -> None:
    pattern = re.compile(rf'^(expression {re.escape(name)} = )"[^"]*"( meta \[.*)$')
    for i, line in enumerate(lines):
        if pattern.match(line):
            escaped = value.replace('"', '""')
            lines[i] = pattern.sub(lambda m: f'{m.group(1)}"{escaped}"{m.group(2)}', line)
            return
    sys.exit(f"Parameter '{name}' not found in expressions.tmdl")


def set_function_body(lines: list[str], mode: str) -> list[str]:
    try:
        start = lines.index("expression fnLoadTable =") + 1
    except ValueError:
        sys.exit("'expression fnLoadTable =' not found in expressions.tmdl")
    end = start
    while end < len(lines) and lines[end].startswith("\t\t"):
        end += 1
    return lines[:start] + ["\t\t" + line for line in TEMPLATES[mode]] + lines[end:]


def apply(definition: Path, mode: str, data_root: Path | None = None,
          sql_endpoint: str | None = None, lakehouse: str = "lh_contoso") -> None:
    """Rewrite <definition>/expressions.tmdl for the given mode (local | fabric | reset)."""
    path = definition / "expressions.tmdl"
    lines, newline = read(path)

    if mode in ("local", "reset"):
        lines = set_function_body(lines, "local")
        data_root = data_root or ROOT / "data" / "marts"
        set_parameter(lines, "DataRoot", PLACEHOLDER_DATA_ROOT if mode == "reset" else str(data_root.resolve()))
        if mode == "reset":
            set_parameter(lines, "SqlEndpoint", PLACEHOLDER_SQL_ENDPOINT)
            set_parameter(lines, "LakehouseName", "lh_contoso")
        elif not (data_root / "fct_sales.parquet").exists():
            print(f"warning: {data_root} has no fct_sales.parquet yet - run the dbt build first")
    elif mode == "fabric":
        if not sql_endpoint:
            sys.exit("fabric mode needs --sql-endpoint (the Lakehouse SQL analytics endpoint host)")
        lines = set_function_body(lines, "fabric")
        set_parameter(lines, "SqlEndpoint", sql_endpoint)
        set_parameter(lines, "LakehouseName", lakehouse)
        set_parameter(lines, "DataRoot", UNUSED)
    else:
        raise ValueError(mode)

    path.write_bytes(newline.join(lines).encode("utf-8"))
    shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    print(f"{shown}: source mode -> {'local' if mode == 'reset' else mode}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["local", "fabric", "status", "reset"])
    parser.add_argument("--definition", type=Path, default=DEFAULT_DEFINITION)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "marts")
    parser.add_argument("--sql-endpoint")
    parser.add_argument("--lakehouse", default="lh_contoso")
    args = parser.parse_args()

    if args.mode == "status":
        lines, _ = read(args.definition / "expressions.tmdl")
        data_root = next((l for l in lines if l.startswith("expression DataRoot")), "")
        print(f"source mode: {current_mode(lines)}")
        print(data_root.split(" meta ")[0])
        return
    apply(args.definition, args.mode, args.data_root, args.sql_endpoint, args.lakehouse)


if __name__ == "__main__":
    main()
