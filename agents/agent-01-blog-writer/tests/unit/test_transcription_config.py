"""Configuration wiring tests for the Increment 6 GCP transcription overlay."""

from __future__ import annotations

from pathlib import Path

import yaml


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def test_gcp_overlay_selects_real_transcription_provider():
    config_dir = Path(__file__).parents[2] / "config"
    base = yaml.safe_load((config_dir / "base.yaml").read_text(encoding="utf-8"))
    gcp = yaml.safe_load((config_dir / "gcp.yaml").read_text(encoding="utf-8"))
    merged = _deep_merge(base, gcp)
    transcription = merged["transcription"]
    assert transcription["provider"] == "gcp"
    assert transcription["normalize_voice"] is True
    assert transcription["cost_per_second_native"] > 0
    assert transcription["provider_currency"] == "USD"
    assert transcription["sync_max_duration_s"] <= 60
    assert transcription["max_duration_s"] > transcription["sync_max_duration_s"]
    assert merged["cost"]["estimated_stage_cost_inr"]["transcribe"] >= 30
    billed_seconds = (
        -(-transcription["max_duration_s"] // transcription["billing_increment_seconds"])
        * transcription["billing_increment_seconds"]
    )
    max_cost_inr = (
        billed_seconds
        * transcription["cost_per_second_native"]
        * merged["cost"]["fx_rates"][transcription["provider_currency"]]
    )
    assert max_cost_inr <= merged["cost"]["ceiling_inr"]
    assert merged["object_storage"]["provider"] == "gcp"
    assert merged["object_storage"]["bucket_secret_key"] == "GCS_BLOG_BUCKET"
