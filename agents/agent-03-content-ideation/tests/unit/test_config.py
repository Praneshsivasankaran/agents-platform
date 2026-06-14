from __future__ import annotations

from pathlib import Path

import yaml


CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def test_cloud_overlay_configs_exist_and_select_providers() -> None:
    expected = {
        "base.yaml": "mock",
        "gcp.yaml": "litellm",
        "bedrock.yaml": "bedrock",
        "azure.yaml": "azure",
    }

    for filename, provider in expected.items():
        cfg = yaml.safe_load((CONFIG_DIR / filename).read_text(encoding="utf-8"))
        assert cfg["provider"] == provider
        assert "llm" in cfg


def test_base_config_registers_billable_stages_and_cost_ceiling() -> None:
    cfg = yaml.safe_load((CONFIG_DIR / "base.yaml").read_text(encoding="utf-8"))

    assert cfg["cost"]["ceiling_inr"] == 20.0
    assert "generate_content_ideas" in cfg["cost"]["estimated_stage_cost_inr"]
    assert "quality_scoring" in cfg["cost"]["estimated_stage_cost_inr"]

