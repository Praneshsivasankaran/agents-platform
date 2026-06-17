"""No-cloud-SDK guard for the shared Demand Generation logic package.

The platform's CI guard (``core.checks.no_cloud_sdk``) only auto-discovers
``agents/*/agent/`` directories. Agents 08-14 delegate their workflow, tools,
scoring, and prompts to ``packages/demand_generation`` — agent business logic
that lives *outside* the guard's scan scope. Without this test that shared logic
could import a cloud/model SDK and the agent-level guards would never notice,
because the agent ``agent/`` dirs are thin wrappers.

This test reuses the guard's AST scanner so a regression in the shared package
fails closed wherever ``pytest packages`` runs.
"""

from __future__ import annotations

from pathlib import Path

from core.checks.no_cloud_sdk import scan


PACKAGE_DIR = Path(__file__).resolve().parents[1]


def test_shared_demand_generation_logic_has_no_cloud_sdk_imports() -> None:
    violations = scan(PACKAGE_DIR)
    assert violations == [], f"forbidden cloud/model SDK import(s) in shared package: {violations}"
