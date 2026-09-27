"""Deploy the Power BI project to a Microsoft Fabric workspace (DEV, TEST or PROD).

Steps:
  1. Ensure the Lakehouse exists and its SQL analytics endpoint is ready (created if missing).
  2. --publish-data: push data/marts/*.parquet to the Lakehouse as Delta tables.
  3. Build a deployable copy of the project in build/fabric/<ENV>/ with the semantic model switched
     to the Fabric source (scripts/set_model_source.py) and pointed at this environment's endpoint.
     The repo itself is never modified.
  4. Publish the semantic model and report with fabric-cicd. The report's byPath reference is
     re-pointed to the deployed model automatically. With --connection-id, the model is bound to a
     Fabric cloud connection (semantic_model_binding), so the first refresh works unattended.
  5. --refresh: run an enhanced refresh (applies the incremental refresh policy) and wait for it.

Usage:
    python scripts/deploy_fabric.py --environment DEV --workspace-id <guid> --publish-data --refresh
Environment variables FABRIC_WORKSPACE_ID, FABRIC_LAKEHOUSE_NAME and FABRIC_CONNECTION_ID can
replace the flags (that is how the GitHub Actions workflow passes per-environment settings).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import set_model_source  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ["ContosoRetail.SemanticModel", "ContosoRetail.Report"]
SEMANTIC_MODEL_NAME = "ContosoRetail"
# Desktop-only files that must never be deployed.
IGNORE = shutil.ignore_patterns(".pbi", "localSettings.json", "cache.abf", "unappliedChanges.json")


def build(environment: str, sql_endpoint: str, lakehouse_name: str, connection_id: str | None) -> Path:
    out = ROOT / "build" / "fabric" / environment
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in ITEMS:
        shutil.copytree(ROOT / "powerbi" / item, out / item, ignore=IGNORE)

    set_model_source.apply(out / ITEMS[0] / "definition", "fabric", sql_endpoint=sql_endpoint, lakehouse=lakehouse_name)

    if connection_id:
        parameters = {
            "semantic_model_binding": {
                "models": [{"semantic_model_name": SEMANTIC_MODEL_NAME, "connection_id": {environment: connection_id}}]
            }
        }
        (out / "parameter.yml").write_text(yaml.safe_dump(parameters, sort_keys=False), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--environment", required=True, help="DEV, TEST or PROD")
    parser.add_argument("--workspace-id", default=os.environ.get("FABRIC_WORKSPACE_ID"))
    parser.add_argument("--lakehouse", default=os.environ.get("FABRIC_LAKEHOUSE_NAME", "lh_contoso"))
    parser.add_argument("--connection-id", default=os.environ.get("FABRIC_CONNECTION_ID") or None,
                        help="Fabric cloud connection (to the Lakehouse SQL endpoint) to bind the model to")
    parser.add_argument("--publish-data", action="store_true", help="upload data/marts to the Lakehouse first")
    parser.add_argument("--refresh", action="store_true", help="refresh the semantic model after deploying")
    parser.add_argument("--prune", action="store_true",
                        help="delete semantic models/reports in the workspace that are not in this repo")
    parser.add_argument("--build-only", action="store_true", help="only create build/fabric/<ENV> (no Fabric calls)")
    parser.add_argument("--sql-endpoint", help="with --build-only: endpoint host to write into the model")
    args = parser.parse_args()
    env = args.environment.upper()

    if args.build_only:
        out = build(env, args.sql_endpoint or "build-only.datawarehouse.fabric.microsoft.com", args.lakehouse, args.connection_id)
        print(f"Build written to {out.relative_to(ROOT)}")
        return

    if not args.workspace_id:
        sys.exit("--workspace-id (or FABRIC_WORKSPACE_ID) is required")

    # Imported late so --build-only works without the Fabric extras (requirements-fabric.txt).
    from fabric_cicd import FabricWorkspace, publish_all_items, unpublish_all_orphan_items
    from fabric_common import FabricClient
    from publish_to_onelake import publish

    client = FabricClient()
    lakehouse = client.ensure_lakehouse(args.workspace_id, args.lakehouse)
    print(f"[{env}] Lakehouse '{lakehouse.name}' ready at {lakehouse.sql_endpoint_host}")

    if args.publish_data:
        publish(client, lakehouse, ROOT / "data" / "marts")
        client.refresh_sql_endpoint_metadata(lakehouse)

    out = build(env, lakehouse.sql_endpoint_host, lakehouse.name, args.connection_id)
    workspace = FabricWorkspace(
        workspace_id=args.workspace_id,
        environment=env,
        repository_directory=str(out),
        item_type_in_scope=["SemanticModel", "Report"],
        token_credential=client.credential,
    )
    publish_all_items(workspace)
    if args.prune:
        unpublish_all_orphan_items(workspace)

    if args.refresh:
        client.refresh_semantic_model(args.workspace_id, SEMANTIC_MODEL_NAME)


if __name__ == "__main__":
    main()
