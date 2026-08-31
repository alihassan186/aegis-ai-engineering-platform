"""Simulator skeleton health check (Step 2.1, FR-080)."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from apps.simulator.config import Settings
from apps.simulator.main import BOOT_MESSAGE, create_app

_SIMULATOR_ROOT = Path(__file__).resolve().parents[3] / "apps" / "simulator"
_FORBIDDEN_IMPORTS = (
    "aegis.api",
    "aegis.application",
    "aegis.domain",
    "sqlalchemy",
)


def test_health_returns_ok_and_app_name() -> None:
    application = create_app(Settings(environment="test", app_name="simulator"))
    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "simulator"}


def test_lifespan_records_boot_message() -> None:
    application = create_app(Settings(environment="test"))
    with TestClient(application) as client:
        client.get("/health")

    assert application.state.boot_message == BOOT_MESSAGE


def test_simulator_does_not_import_aegis_core_or_sqlalchemy() -> None:
    names: set[str] = set()
    for py_file in _SIMULATOR_ROOT.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)

    forbidden = [
        module
        for module in names
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in _FORBIDDEN_IMPORTS)
    ]
    assert forbidden == []
