"""No-cloud-SDK guard for the shared Marketing Operations logic package."""

from __future__ import annotations

from pathlib import Path

from core.checks.no_cloud_sdk import scan


PACKAGE_DIR = Path(__file__).resolve().parents[1]


def test_shared_marketing_operations_logic_has_no_cloud_sdk_imports() -> None:
    violations = scan(PACKAGE_DIR)
    assert violations == [], f"forbidden cloud/model SDK import(s) in shared package: {violations}"
