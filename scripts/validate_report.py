"""Validate the Power BI project's report (PBIR) and item files without opening Power BI Desktop.

Checks:
  1. Every JSON file that declares a "$schema" validates against Microsoft's published schema
     (definition.pbir, report.json, pages, visuals, .platform, .pbip, .pbism). Schemas are cached
     in .cache/schemas.
  2. Custom themes validate against the Power BI report theme schema.
  3. Every table/column/measure that a visual or filter references exists in the semantic model
     (TMDL), so a renamed measure fails CI instead of showing a broken visual after deployment.
  4. PBIR naming rules: folder names match object names, pages.json lists real pages, and every
     registered resource file exists.

Usage:
    python scripts/validate_report.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
CACHE = ROOT / ".cache" / "schemas"
THEME_SCHEMA_URL = (
    "https://raw.githubusercontent.com/microsoft/powerbi-desktop-samples/main/"
    "Report%20Theme%20JSON%20Schema/reportThemeSchema-2.157.json"
)
NAME_RULE = re.compile(r"^[\w-]+$")

errors: list[str] = []


def error(where: Path | str, message: str) -> None:
    rel = where.relative_to(ROOT) if isinstance(where, Path) else where
    errors.append(f"{rel}: {message}")


def fetch_schema(url: str) -> dict:
    parsed = urlparse(url)
    cached = CACHE / parsed.netloc / parsed.path.lstrip("/").replace("%20", " ")
    if not cached.exists():
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(resp.content)
    return json.loads(cached.read_text(encoding="utf-8-sig"))


REGISTRY = Registry(retrieve=lambda uri: Resource.from_contents(fetch_schema(uri), default_specification=DRAFT7))


def validate(path: Path, document: dict, schema_url: str) -> None:
    validator = Draft7Validator(fetch_schema(schema_url), registry=REGISTRY)
    for e in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))[:10]:
        pointer = "/".join(str(p) for p in e.absolute_path) or "<root>"
        error(path, f"schema: {pointer}: {e.message[:300]}")


def load_model_objects(definition: Path) -> dict[str, set[str]]:
    """Table name -> column/measure/hierarchy names, parsed from TMDL."""
    objects: dict[str, set[str]] = {}
    for tmdl in (definition / "tables").glob("*.tmdl"):
        text = tmdl.read_text(encoding="utf-8")
        table = re.search(r"^table (.+)$", text, re.MULTILINE).group(1).strip()
        names = re.findall(r"^\t(?:column|measure|hierarchy) (.+?)(?: =.*)?$", text, re.MULTILINE)
        objects[unquote(table)] = {unquote(n.strip()) for n in names}
    return objects


def unquote(name: str) -> str:
    return name[1:-1].replace("''", "'") if name.startswith("'") and name.endswith("'") else name


def field_references(node, found=None):
    """Yield (entity, property) pairs for every Column/Measure/Hierarchy reference in a PBIR tree."""
    found = [] if found is None else found
    if isinstance(node, dict):
        for kind in ("Column", "Measure", "Hierarchy"):
            ref = node.get(kind)
            if isinstance(ref, dict) and "Property" in ref:
                entity = ref.get("Expression", {}).get("SourceRef", {}).get("Entity")
                if entity:
                    found.append((entity, ref.get("Property") or ref.get("Hierarchy")))
        for key, value in node.items():
            if key == "From" and isinstance(value, list):  # filter aliases
                found.extend((f["Entity"], None) for f in value if "Entity" in f)
            else:
                field_references(value, found)
    elif isinstance(node, list):
        for item in node:
            field_references(item, found)
    return found


def check_report(report_dir: Path) -> None:
    pbir = json.loads((report_dir / "definition.pbir").read_text(encoding="utf-8"))
    model_path = pbir.get("datasetReference", {}).get("byPath", {}).get("path")
    model = load_model_objects((report_dir / model_path / "definition").resolve()) if model_path else None

    definition = report_dir / "definition"
    pages_meta = json.loads((definition / "pages" / "pages.json").read_text(encoding="utf-8"))
    page_dirs = {p.name: p for p in (definition / "pages").iterdir() if p.is_dir()}
    for name in pages_meta.get("pageOrder", []):
        if name not in page_dirs:
            error(definition / "pages" / "pages.json", f"pageOrder lists '{name}' but no such page folder exists")

    for page_dir in page_dirs.values():
        page = json.loads((page_dir / "page.json").read_text(encoding="utf-8"))
        if page["name"] != page_dir.name or not NAME_RULE.match(page_dir.name):
            error(page_dir / "page.json", f"page name '{page['name']}' must match folder and be [A-Za-z0-9_-]")
        for visual_file in (page_dir / "visuals").glob("*/visual.json"):
            visual = json.loads(visual_file.read_text(encoding="utf-8"))
            if visual["name"] != visual_file.parent.name or not NAME_RULE.match(visual["name"]):
                error(visual_file, f"visual name '{visual['name']}' must match folder and be [A-Za-z0-9_-]")
            if model is None:
                continue
            for entity, prop in field_references(visual):
                if entity not in model:
                    error(visual_file, f"unknown table '{entity}'")
                elif prop is not None and prop not in model[entity]:
                    error(visual_file, f"'{entity}' has no column/measure/hierarchy '{prop}'")

    report = json.loads((definition / "report.json").read_text(encoding="utf-8"))
    for package in report.get("resourcePackages", []):
        for item in package.get("items", []):
            resource = report_dir / "StaticResources" / package["name"] / item["path"]
            if not resource.exists():
                error(definition / "report.json", f"resource '{item['path']}' not found at {resource.relative_to(ROOT)}")
            elif item["type"] == "CustomTheme":
                validate(resource, json.loads(resource.read_text(encoding="utf-8-sig")), THEME_SCHEMA_URL)


def main() -> int:
    candidates = [p for p in PBI.rglob("*") if p.is_file() and (p.suffix in {".json", ".pbir", ".pbism", ".pbip"} or p.name == ".platform")]
    validated = 0
    for path in candidates:
        if "StaticResources" in path.parts or ".pbi" in path.parts:
            continue
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        schema_url = document.get("$schema") if isinstance(document, dict) else None
        if schema_url:
            validate(path, document, schema_url)
            validated += 1

    for report_dir in PBI.glob("*.Report"):
        check_report(report_dir)

    for e in errors:
        print(f"ERROR {e}")
    print(f"Validated {validated} files against their JSON schemas; report checks "
          f"{'passed' if not errors else f'failed with {len(errors)} error(s)'}.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
