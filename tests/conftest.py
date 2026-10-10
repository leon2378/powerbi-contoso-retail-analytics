"""Shared setup for the unit tests of the scripts in scripts/.

Run with: python -m pytest -q tests   (or .\\tasks.ps1 check, which CI mirrors)
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _stub_azure_identity() -> None:
    """fabric_common imports azure-identity, which only requirements-fabric.txt installs. The tests
    never authenticate, so empty stand-ins are enough when the real package is missing."""
    try:
        import azure.identity  # noqa: F401
        return
    except ImportError:
        pass
    azure = types.ModuleType("azure")
    azure.__path__ = []
    core = types.ModuleType("azure.core")
    core.__path__ = []
    credentials = types.ModuleType("azure.core.credentials")
    credentials.TokenCredential = object
    identity = types.ModuleType("azure.identity")
    for name in ("AzureCliCredential", "ClientSecretCredential", "InteractiveBrowserCredential"):
        setattr(identity, name, type(name, (), {}))
    sys.modules.update({
        "azure": azure,
        "azure.core": core,
        "azure.core.credentials": credentials,
        "azure.identity": identity,
    })


_stub_azure_identity()
