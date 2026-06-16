from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_required_config_overlays_exist() -> None:
    for name in ("base.yaml", "gcp.yaml", "bedrock.yaml", "azure.yaml"):
        assert (ROOT / "config" / name).exists()


def test_gcp_uses_existing_vertex_project_convention() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "gcp.yaml").read_text(encoding="utf-8"))
    assert cfg["llm"]["vertex_project_secret"] == "VERTEX_AI_PROJECT"
    assert cfg["llm"]["provider"] == "litellm"
