"""Add missing lineageTag properties to hand-written TMDL.

Power BI Desktop's report layer binds visuals to model objects through their lineage tags. A measure
added to TMDL by hand, without a lineageTag, is loaded into the engine but silently dropped from
every visual that uses it. This script gives each table, column, measure and hierarchy that lacks
one a stable tag (a UUID derived from the object's table and name, so re-running is idempotent and
the same object gets the same tag on every machine).

Usage:
    python scripts/add_lineage_tags.py            # fix in place
    python scripts/add_lineage_tags.py --check    # exit 1 if any tag is missing (CI)
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "powerbi" / "ContosoRetail.SemanticModel" / "definition" / "tables"
NAMESPACE = uuid.UUID("5b0c7a4e-2f1d-4b8e-9c6a-3d2e1f0a9b8c")
OBJECT = re.compile(r"^(\t?)(table|measure|column|hierarchy) (.+?)(?: =.*)?$")


def tag_for(table: str, kind: str, name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{table}/{kind}/{name}"))


def process(text: str) -> tuple[str, list[str]]:
    lines = text.split("\n")
    table = None
    out, added = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = OBJECT.match(line)
        if not m:
            out.append(line)
            i += 1
            continue
        indent, kind, name = m.group(1), m.group(2), m.group(3).strip()
        if kind == "table":
            table = name
        prop_indent = indent + "\t"
        # The object's block: following lines indented deeper than the header.
        j = i + 1
        while j < len(lines) and (lines[j].startswith(prop_indent) or lines[j].strip() == ""):
            if lines[j].strip() == "" and j + 1 < len(lines) and not lines[j + 1].startswith(prop_indent):
                break
            j += 1
        block = lines[i + 1:j]
        own_props = [b for b in block if b.startswith(prop_indent) and not b.startswith(prop_indent + "\t")]
        if any(b.strip().startswith("lineageTag:") for b in own_props):
            out.append(line)
            i += 1
            continue
        # Insert as the first property: after any multi-line expression body (deeper indentation).
        k = 0
        while k < len(block) and (block[k].startswith(prop_indent + "\t") or block[k].strip() == "" and k + 1 < len(block) and block[k + 1].startswith(prop_indent + "\t")):
            k += 1
        new_tag = f"{prop_indent}lineageTag: {tag_for(table or name, kind, name)}"
        out.append(line)
        out.extend(block[:k])
        out.append(new_tag)
        out.extend(block[k:])
        added.append(f"{kind} {name}")
        i = j
    return "\n".join(out), added


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    total = []
    for path in sorted(TABLES.glob("*.tmdl")):
        raw = path.read_bytes().decode("utf-8-sig")
        newline = "\r\n" if "\r\n" in raw else "\n"
        fixed, added = process(raw.replace("\r\n", "\n"))
        if added:
            total += [f"{path.name}: {a}" for a in added]
            if not args.check:
                path.write_bytes(fixed.replace("\n", newline).encode("utf-8"))
    for t in total:
        print(("MISSING " if args.check else "tagged  ") + t)
    if args.check and total:
        print("Run: python scripts/add_lineage_tags.py")
        return 1
    print(f"{len(total)} object(s) {'missing a lineageTag' if args.check else 'tagged'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
