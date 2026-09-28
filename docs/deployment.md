# Deploying to Microsoft Fabric

The deploy pipeline (`.github/workflows/deploy.yml` → `scripts/deploy_fabric.py`) does, per environment:

1. Builds the dbt marts from the Contoso release (`CONTOSO_SIZE`, default `1m`).
2. Ensures the Lakehouse exists (created with schemas enabled if missing) and its SQL analytics endpoint is ready.
3. Publishes every mart as a Delta table (`Tables/dbo/<mart>`), then asks the endpoint to sync metadata.
4. Builds `build/fabric/<ENV>/`: a copy of the project with the model switched to the Fabric source and pointed at this environment's endpoint. The repository itself is never modified.
5. Publishes the semantic model and report with [fabric-cicd](https://github.com/microsoft/fabric-cicd). The report's `byPath` reference is re-pointed to the deployed model automatically.
6. Binds the model to a cloud connection (if `FABRIC_CONNECTION_ID` is set) and runs an enhanced refresh that applies the incremental refresh policy.

## One-time setup

### 1. Capacity and workspaces

- A Fabric capacity: a trial, or an F SKU (F2 is enough for the 1M dataset).
- Three workspaces on that capacity, for example `Contoso Retail [DEV]`, `[TEST]` and `[PROD]`. Note each workspace ID (the GUID in the URL after `/groups/`).

### 2. Service principal with GitHub OIDC (no client secret)

1. Create an app registration in Microsoft Entra ID.
2. Under **Certificates & secrets → Federated credentials**, add a *GitHub Actions* credential per environment:
   organisation/repo, entity type **Environment**, names `DEV`, `TEST`, `PROD`.
3. Add the service principal to a security group, and in the **Fabric admin portal → Tenant settings → Developer settings**, enable *Service principals can use Fabric APIs* for that group.
4. Give the service principal the **Contributor** role (or higher) on each workspace.

### 3. Data connection for the semantic model

After the first deploy, the model needs credentials for the Lakehouse SQL endpoint. Either:

- **Automated (recommended):** in Fabric, go to *Settings → Manage connections and gateways → New → Cloud* and create a *SQL Server* connection to the environment's SQL endpoint host and Lakehouse name, using OAuth 2.0 or service-principal authentication. Share it with the service principal and put its ID in `FABRIC_CONNECTION_ID`. fabric-cicd then binds the model on every deploy (`semantic_model_binding`).
- **Manual:** after the first deploy, open *Semantic model → Settings → Data source credentials* and sign in with OAuth. The binding persists across later deploys.

### 4. GitHub configuration

| Where | Name | Value |
|---|---|---|
| Repository variable | `FABRIC_ENABLED` | `true` (the deploy workflow does nothing until this is set) |
| Environment `DEV` / `TEST` / `PROD`: variables | `FABRIC_WORKSPACE_ID` | workspace GUID |
| | `FABRIC_LAKEHOUSE_NAME` | optional, default `lh_contoso` |
| | `FABRIC_CONNECTION_ID` | optional, cloud connection GUID (step 3) |
| | `CONTOSO_SIZE` | optional: `100k`, `1m` (default) or `10m` |
| Environment secrets | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` | from the app registration |
| Environment `PROD` protection | Required reviewers | yourself or the release owner |

`main` → DEV runs on every push. For TEST and PROD, run **Actions → Deploy to Fabric → Run workflow** and pick the environment.

### 5. Row-level security

Role *membership* is workspace-specific, so it is not stored in source control. In each workspace, open *Semantic model → Security*:

- **Regional Manager**: add regional managers. What they see comes from `transform/seeds/rls_user_access.csv`. Replace the `example` UPNs with real Microsoft Entra UPNs.
- **Global Viewer**: executives and finance (no filter).

Once a model has roles, any viewer who is not in a role sees no data. Test with **View as** before sharing.

## Deploying from your machine

```powershell
az login
.\tasks.ps1 setup -Fabric
.\tasks.ps1 all -Size 1m
.\tasks.ps1 deploy -Environment DEV -WorkspaceId <workspace-guid>
```

`python scripts/deploy_fabric.py --environment DEV --build-only` produces the deployable folder without calling Fabric. Use it to inspect exactly what will be published.

Without the Azure CLI, sign in through the browser instead: set `FABRIC_AUTH=browser` (and `AZURE_TENANT_ID` if your account
belongs to several tenants). To deploy another dataset size than the one in `data/marts`, pass `--marts-dir`, e.g.
`python scripts/deploy_fabric.py --environment DEV --workspace-id <guid> --publish-data --marts-dir data/10m/marts --refresh`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Refresh fails: *table not found* right after publishing data | The SQL endpoint's metadata sync lags behind OneLake. The script triggers a sync; if your tenant doesn't expose that API, wait a minute and refresh again. |
| Refresh fails: *credentials are missing or invalid* | Configure the connection (step 3). |
| `401/403` from Fabric APIs | The service principal lacks workspace access, or the *Service principals can use Fabric APIs* tenant setting is off. |
| Report opens but visuals are empty | RLS: the viewer isn't in a role, or their UPN isn't in `rls_user_access.csv`. |
| Old data outside the incremental window disappears | The policy keeps 15 years (`rollingWindowPeriods` in `tables/Sales.tmdl`). Adjust it to your retention rules. |
