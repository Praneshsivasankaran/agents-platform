from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from core.cost import resolve_is_mock


ROOT = Path(__file__).resolve().parents[2]


def test_cloud_overlay_must_clear_mock_bypass() -> None:
    base = yaml.safe_load((ROOT / "config" / "base.yaml").read_text(encoding="utf-8"))
    bad = copy.deepcopy(base)
    bad["llm"]["provider"] = "litellm"
    bad["provider"] = "litellm"
    bad["cost"]["is_mock"] = True

    with pytest.raises(ValueError):
        resolve_is_mock(bad)
