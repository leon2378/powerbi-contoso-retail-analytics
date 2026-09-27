<#
.SYNOPSIS
    Task runner for the Contoso Retail Analytics project (Windows PowerShell 5.1+ / PowerShell 7).

.EXAMPLE
    .\tasks.ps1 setup                 # create .venv and install dependencies
    .\tasks.ps1 all -Size 1m          # download data, dbt build, validate, point the model at data/marts
    .\tasks.ps1 check                 # everything CI runs (fixture data, no download)
    .\tasks.ps1 deploy -Environment DEV -WorkspaceId <guid>
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "setup", "data", "fixtures", "build", "docs", "check", "dictionary", "model-local", "model-reset",
                 "model-status", "publish", "deploy", "all", "clean")]
    [string]$Task = "help",

    [ValidateSet("100k", "1m", "10m")]
    [string]$Size = "100k",

    [ValidateSet("DEV", "TEST", "PROD")]
    [string]$Environment = "DEV",

    [string]$WorkspaceId = $env:FABRIC_WORKSPACE_ID,

    [switch]$Fabric  # with 'setup': also install the Fabric deployment extras
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$Dbt = Join-Path $PSScriptRoot ".venv\Scripts\dbt.exe"
$DbtArgs = @("--project-dir", "transform", "--profiles-dir", "transform")

function Invoke-Step([string]$Name, [scriptblock]$Command) {
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Step failed: $Name (exit code $LASTEXITCODE)" }
}

function Assert-Venv {
    if (-not (Test-Path $Python)) { throw "No virtual environment yet. Run: .\tasks.ps1 setup" }
}

function New-DataDirs {
    foreach ($dir in "data\marts", "data\warehouse") { New-Item -ItemType Directory -Force $dir | Out-Null }
}

switch ($Task) {
    "help" {
        @"
Usage: .\tasks.ps1 <task> [-Size 100k|1m|10m] [-Environment DEV|TEST|PROD] [-WorkspaceId <guid>]

Tasks:
  setup [-Fabric]        Create .venv and install requirements (add -Fabric for deployment extras)
  data [-Size 100k]      Download a Contoso V2 Parquet release into data\raw
  fixtures               Generate small synthetic data into data\raw (offline / CI)
  build                  dbt build: staging -> marts (+ tests), exports data\marts\*.parquet
  docs                   Generate and serve dbt docs (lineage graph) on http://localhost:8080
  check                  Everything CI runs, on fixture data in data\ci
  dictionary             Regenerate docs\data-dictionary.md from the model's descriptions
  model-local            Point the Power BI model at data\marts (local Parquet mode)
  model-reset            Restore the committed model state (placeholder path), run before committing
  model-status           Show the model's current source mode
  publish -WorkspaceId   Publish data\marts to the Fabric Lakehouse as Delta tables
  deploy -Environment -WorkspaceId   Publish data, deploy model + report, refresh
  all [-Size 100k]       data + build + model-local, ready to open powerbi\ContosoRetail.pbip
  clean                  Remove data, build output and dbt target
"@ | Write-Host
    }

    "setup" {
        if (-not (Test-Path $Python)) { Invoke-Step "Create virtual environment" { python -m venv .venv } }
        Invoke-Step "Install requirements" { & $Python -m pip install --upgrade pip -q; & $Python -m pip install -r requirements.txt -q }
        if ($Fabric) { Invoke-Step "Install Fabric extras" { & $Python -m pip install -r requirements-fabric.txt -q } }
    }

    "data" {
        Assert-Venv
        Invoke-Step "Download Contoso V2 ($Size)" { & $Python scripts\download_contoso.py --size $Size }
    }

    "fixtures" {
        Assert-Venv
        Invoke-Step "Generate fixture data" { & $Python scripts\make_fixture_data.py --out data\raw }
    }

    "build" {
        Assert-Venv
        New-DataDirs
        Invoke-Step "dbt build" { & $Dbt build @DbtArgs }
    }

    "docs" {
        Assert-Venv
        Invoke-Step "dbt docs generate" { & $Dbt docs generate @DbtArgs }
        & $Dbt docs serve @DbtArgs --port 8080
    }

    "check" {
        Assert-Venv
        # Isolated from your real data: CI-equivalent run on fixtures in data\ci.
        $env:CONTOSO_RAW_DIR = "data/ci/raw"; $env:CONTOSO_MARTS_DIR = "data/ci/marts"; $env:DUCKDB_PATH = "data/ci/ci.duckdb"
        try {
            New-Item -ItemType Directory -Force "data\ci\marts" | Out-Null
            Invoke-Step "Fixture data" { & $Python scripts\make_fixture_data.py --out data\ci\raw }
            Invoke-Step "dbt build" { & $Dbt build @DbtArgs }
        }
        finally {
            Remove-Item Env:CONTOSO_RAW_DIR, Env:CONTOSO_MARTS_DIR, Env:DUCKDB_PATH -ErrorAction SilentlyContinue
        }
        Invoke-Step "Contract check (dbt <-> model)" { & $Python scripts\check_model_contract.py }
        Invoke-Step "Lineage tags present" { & $Python scripts\add_lineage_tags.py --check }
        Invoke-Step "Data dictionary up to date" { & $Python scripts\generate_data_dictionary.py --check }
        Invoke-Step "Report checks (PBIR)" { & $Python scripts\validate_report.py }
        Invoke-Step "TMDL validation" { dotnet run --project ci\TmdlValidator -- powerbi\ContosoRetail.SemanticModel\definition --bim build\model.bim }
        Write-Host "All checks passed. (The Best Practice Analyzer runs in CI with Tabular Editor 2.)" -ForegroundColor Green
    }

    "dictionary"   { Assert-Venv; Invoke-Step "Regenerate docs\data-dictionary.md" { & $Python scripts\generate_data_dictionary.py } }
    "model-local"  { Assert-Venv; Invoke-Step "Model -> local Parquet" { & $Python scripts\set_model_source.py local } }
    "model-reset"  { Assert-Venv; Invoke-Step "Model -> committed state" { & $Python scripts\set_model_source.py reset } }
    "model-status" { Assert-Venv; & $Python scripts\set_model_source.py status }

    "publish" {
        Assert-Venv
        if (-not $WorkspaceId) { throw "Pass -WorkspaceId <guid> or set FABRIC_WORKSPACE_ID" }
        Invoke-Step "Publish marts to OneLake" { & $Python scripts\publish_to_onelake.py --workspace-id $WorkspaceId }
    }

    "deploy" {
        Assert-Venv
        if (-not $WorkspaceId) { throw "Pass -WorkspaceId <guid> or set FABRIC_WORKSPACE_ID" }
        Invoke-Step "Deploy to $Environment" {
            & $Python scripts\deploy_fabric.py --environment $Environment --workspace-id $WorkspaceId --publish-data --refresh
        }
    }

    "all" {
        & $PSCommandPath data -Size $Size
        & $PSCommandPath build
        & $PSCommandPath model-local
        Write-Host "`nReady. Open powerbi\ContosoRetail.pbip in Power BI Desktop and click Refresh." -ForegroundColor Green
    }

    "clean" {
        foreach ($path in "data", "build", "transform\target", "transform\logs") {
            if (Test-Path $path) { Remove-Item -Recurse -Force $path }
        }
        Write-Host "Cleaned."
    }
}
