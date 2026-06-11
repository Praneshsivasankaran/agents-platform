"""Config loading + provider-selection inputs (DESIGN §4.2, §8.3).

Cloud + provider + tier→model maps + FX rate + caps are read from YAML (``base.yaml`` = offline
mock; ``gcp.yaml``; ``bedrock.yaml``; ``azure.yaml``). Agent logic never branches on cloud — it asks
the factory for a provider and a tier.

Cloud-neutral by construction: standard library + PyYAML; never a cloud SDK.
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml


def load_config(path: str | pathlib.Path) -> dict[str, Any]:
    """Load a YAML config file into a plain dict (mapping required)."""
    with pathlib.Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config at {path} must be a YAML mapping, got {type(data).__name__}")
    return data
