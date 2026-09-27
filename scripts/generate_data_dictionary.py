"""Generate docs/data-dictionary.md from the semantic model (TMDL).

Measure and table descriptions live next to the DAX as `///` comments, so the documentation cannot
drift from the model. CI runs this with --check and fails if the committed file is stale.

Usage:
    python scripts/generate_data_dictionary.py          # rewrite docs/data-dictionary.md
    python scripts/generate_data_dictionary.py --check  # exit 1 if it is out of date
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "powerbi" / "ContosoRetail.SemanticModel" / "definition" / "tables"
OUTPUT = ROOT / "docs" / "data-dictionary.md"


@dataclass
class Measure:
    name: str
    description: str
    folder: str = ""
    format: str = ""
    expression: str = ""


@dataclass
class Column:
    name: str
    data_type: str
    description: str
    hidden: bool


@dataclass
class Table:
    name: str
    description: str
    hidden: bool = False
    measures: list[Measure] = field(default_factory=list)
    columns: list[Column] = field(default_factory=list)


def unquote(name: str) -> str:
    name = name.strip()
    return name[1:-1].replace("''", "'") if name.startswith("'") else name


def parse(path: Path) -> Table:
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    doc: list[str] = []
    table: Table | None = None
    current = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("table "):
            table = Table(unquote(line[6:]), " ".join(doc))
            doc = []
        elif line.startswith("\t///") or line.startswith("///"):
            doc.append(line.split("///", 1)[1].strip())
        elif line.startswith("\tmeasure "):
            head, _, inline = line[len("\tmeasure "):].partition(" = ")
            body = [inline.strip()] if inline.strip() else []
            while i + 1 < len(lines) and lines[i + 1].startswith("\t\t\t"):
                i += 1
                body.append(lines[i][3:])
            current = Measure(unquote(head.rstrip(" =")), " ".join(doc), expression="\n".join(body).strip())
            table.measures.append(current)
            doc = []
        elif line.startswith("\tcolumn "):
            current = Column(unquote(line[len("\tcolumn "):]), "", " ".join(doc), False)
            table.columns.append(current)
            doc = []
        elif line == "\tisHidden" and table is not None:
            table.hidden = True
        elif line.startswith("\t\t") and current is not None:
            prop = line.strip()
            if isinstance(current, Measure) and prop.startswith("displayFolder:"):
                current.folder = prop.split(":", 1)[1].strip()
            elif isinstance(current, Measure) and prop.startswith("formatString:"):
                current.format = prop.split(":", 1)[1].strip()
            elif isinstance(current, Measure) and prop.startswith("formatStringDefinition"):
                current.format = "dynamic"
            elif isinstance(current, Column) and prop.startswith("dataType:"):
                current.data_type = prop.split(":", 1)[1].strip()
            elif isinstance(current, Column) and prop == "isHidden":
                current.hidden = True
        elif line.startswith("\t") and not line.startswith("\t\t") and line.strip():
            current = None if not line.startswith("\t///") else current
        i += 1
    return table


def render(tables: list[Table]) -> str:
    out = [
        "# Data dictionary",
        "",
        "Generated from the semantic model by `scripts/generate_data_dictionary.py`. Do not edit by hand:",
        "change the `///` descriptions in the TMDL files instead.",
        "",
        "## Measures",
        "",
    ]
    measures = [m for t in tables for m in t.measures]
    for folder in sorted({m.folder for m in measures}):
        out += [f"### {folder or 'Other'}", "", "| Measure | Description | Format |", "|---|---|---|"]
        for m in [m for m in measures if m.folder == folder]:
            fmt = f"`{m.format}`" if m.format and m.format != "dynamic" else m.format
            out.append(f"| **{m.name}** | {m.description} | {fmt} |")
        out.append("")
        for m in [m for m in measures if m.folder == folder]:
            out += [f"<details><summary>DAX: {m.name}</summary>", "", "```dax", m.expression, "```", "", "</details>", ""]

    out += ["## Tables", ""]
    for t in tables:
        visible = [c for c in t.columns if not c.hidden]
        if not visible and not t.hidden:
            continue  # e.g. the measures home table
        out += [f"### {t.name}{' (hidden)' if t.hidden else ''}", "", t.description or "", ""]
        if visible:
            out += ["| Column | Type | Description |", "|---|---|---|"]
            out += [f"| {c.name} | {c.data_type} | {c.description} |" for c in visible]
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    order = ["_Measures", "Sales", "Budget", "Date", "Customer", "Product", "Store", "Time Intelligence",
             "Metric Selector", "Security Access"]
    tables = sorted((parse(p) for p in TABLES.glob("*.tmdl")), key=lambda t: order.index(t.name) if t.name in order else 99)
    content = render(tables)

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8").replace("\r\n", "\n") if OUTPUT.exists() else ""
        if current != content:
            print(f"{OUTPUT.relative_to(ROOT)} is out of date. Run: python scripts/generate_data_dictionary.py")
            return 1
        print("Data dictionary is up to date.")
        return 0

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len([m for t in tables for m in t.measures])} measures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
