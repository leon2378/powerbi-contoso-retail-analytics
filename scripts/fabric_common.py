"""Shared helpers for talking to Microsoft Fabric and the Power BI REST API.

Authentication (no secrets in code):
  * CI / service principal: set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, or use
    azure/login with OIDC in GitHub Actions (then the Azure CLI credential is used).
  * Local development: run `az login` first, or set FABRIC_AUTH=browser to sign in through the web
    browser instead (no Azure CLI needed; AZURE_TENANT_ID picks the tenant if you have several).
The identity needs Contributor (or higher) on the target workspace, and the tenant must allow
service principals to use Fabric APIs.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests
from azure.core.credentials import TokenCredential
from azure.identity import AzureCliCredential, ClientSecretCredential, InteractiveBrowserCredential

FABRIC_API = "https://api.fabric.microsoft.com/v1"
POWERBI_API = "https://api.powerbi.com/v1.0/myorg"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
STORAGE_SCOPE = "https://storage.azure.com/.default"


def get_credential() -> TokenCredential:
    if os.environ.get("AZURE_CLIENT_SECRET"):
        return ClientSecretCredential(
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
        )
    if os.environ.get("FABRIC_AUTH", "").lower() == "browser":
        # One sign-in per run: the credential reuses its token for the Fabric, Power BI and storage scopes.
        return InteractiveBrowserCredential(tenant_id=os.environ.get("AZURE_TENANT_ID"))
    return AzureCliCredential()


@dataclass
class Lakehouse:
    id: str
    name: str
    workspace_id: str
    sql_endpoint_id: str | None
    sql_endpoint_host: str | None
    default_schema: str | None

    @property
    def tables_uri(self) -> str:
        """abfss:// URI of the Tables folder (GUID form works for schema and non-schema lakehouses)."""
        base = f"abfss://{self.workspace_id}@onelake.dfs.fabric.microsoft.com/{self.id}/Tables"
        return f"{base}/{self.default_schema}" if self.default_schema else base


class FabricClient:
    def __init__(self, credential: TokenCredential | None = None):
        self.credential = credential or get_credential()
        self.session = requests.Session()

    # --- low level ----------------------------------------------------------------------------
    def _headers(self, scope: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.credential.get_token(scope).token}"}

    def request(self, method: str, url: str, scope: str = FABRIC_SCOPE, **kwargs) -> requests.Response:
        for attempt in range(6):
            resp = self.session.request(method, url, headers=self._headers(scope), timeout=60, **kwargs)
            if resp.status_code != 429:
                break
            time.sleep(int(resp.headers.get("Retry-After", 2 ** attempt)))
        if resp.status_code >= 400:
            raise RuntimeError(f"{method} {url} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    def wait_for_operation(self, resp: requests.Response, timeout_s: int = 600) -> None:
        """Poll a Fabric long-running operation (202 + Location header) until it finishes."""
        if resp.status_code != 202 or "Location" not in resp.headers:
            return
        location, deadline = resp.headers["Location"], time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(int(resp.headers.get("Retry-After", 5)))
            resp = self.request("GET", location)
            status = resp.json().get("status") if resp.content else None
            if status in ("Succeeded", None):
                return
            if status in ("Failed", "Cancelled"):
                raise RuntimeError(f"Operation {status}: {resp.text[:500]}")
        raise TimeoutError(f"Operation did not finish within {timeout_s}s: {location}")

    # --- lakehouse ------------------------------------------------------------------------------
    def get_lakehouse(self, workspace_id: str, name: str) -> Lakehouse | None:
        items = self.request("GET", f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses").json()["value"]
        match = next((i for i in items if i["displayName"] == name), None)
        if match is None:
            return None
        detail = self.request("GET", f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses/{match['id']}").json()
        props = detail.get("properties") or {}
        sql = props.get("sqlEndpointProperties") or {}
        ready = sql.get("provisioningStatus") == "Success"
        return Lakehouse(
            id=detail["id"],
            name=detail["displayName"],
            workspace_id=workspace_id,
            sql_endpoint_id=sql.get("id") if ready else None,
            sql_endpoint_host=sql.get("connectionString") if ready else None,
            default_schema=props.get("defaultSchema"),
        )

    def ensure_lakehouse(self, workspace_id: str, name: str, timeout_s: int = 900) -> Lakehouse:
        """Return the lakehouse, creating it (schemas enabled) if needed, once its SQL endpoint is ready."""
        if self.get_lakehouse(workspace_id, name) is None:
            print(f"Creating lakehouse '{name}'")
            resp = self.request(
                "POST",
                f"{FABRIC_API}/workspaces/{workspace_id}/lakehouses",
                json={"displayName": name, "creationPayload": {"enableSchemas": True}},
            )
            self.wait_for_operation(resp)
        deadline = time.time() + timeout_s
        while True:
            lakehouse = self.get_lakehouse(workspace_id, name)
            if lakehouse and lakehouse.sql_endpoint_host:
                return lakehouse
            if time.time() > deadline:
                raise TimeoutError(f"SQL analytics endpoint for '{name}' was not provisioned in time")
            print("  waiting for the SQL analytics endpoint to provision...")
            time.sleep(15)

    def refresh_sql_endpoint_metadata(self, lakehouse: Lakehouse) -> None:
        """Ask the SQL analytics endpoint to pick up new Delta tables now instead of on its own schedule."""
        if not lakehouse.sql_endpoint_id:
            return
        try:
            resp = self.request(
                "POST",
                f"{FABRIC_API}/workspaces/{lakehouse.workspace_id}/sqlEndpoints/{lakehouse.sql_endpoint_id}/refreshMetadata",
                json={},
            )
            self.wait_for_operation(resp)
            print("SQL analytics endpoint metadata refreshed")
        except RuntimeError as exc:  # best effort: the endpoint also syncs automatically
            print(f"warning: metadata refresh not triggered ({exc}); the endpoint will sync on its own")

    # --- semantic model refresh -------------------------------------------------------------
    def refresh_semantic_model(self, workspace_id: str, name: str, timeout_s: int = 3600) -> None:
        datasets = self.request("GET", f"{POWERBI_API}/groups/{workspace_id}/datasets", scope=POWERBI_SCOPE).json()["value"]
        dataset = next((d for d in datasets if d["name"] == name), None)
        if dataset is None:
            raise RuntimeError(f"Semantic model '{name}' not found in workspace {workspace_id}")
        url = f"{POWERBI_API}/groups/{workspace_id}/datasets/{dataset['id']}/refreshes"
        # Enhanced refresh: applies the incremental refresh policy and commits atomically.
        resp = self.request("POST", url, scope=POWERBI_SCOPE,
                            json={"type": "full", "commitMode": "transactional", "applyRefreshPolicy": True})
        request_id = resp.headers.get("RequestId") or resp.headers.get("x-ms-request-id")
        print(f"Refresh of '{name}' started")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(20)
            latest = self.request("GET", f"{url}?$top=1", scope=POWERBI_SCOPE).json()["value"][0]
            status = latest.get("status")
            if status == "Completed":
                print(f"Refresh completed ({latest.get('startTime')} -> {latest.get('endTime')})")
                return
            if status in ("Failed", "Cancelled", "Disabled"):
                raise RuntimeError(f"Refresh {status}: {latest.get('serviceExceptionJson')} (request {request_id})")
            print(f"  refresh {status or 'in progress'}...")
        raise TimeoutError("Semantic model refresh did not finish in time")
