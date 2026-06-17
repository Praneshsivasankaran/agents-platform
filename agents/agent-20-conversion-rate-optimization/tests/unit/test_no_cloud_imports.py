from __future__ import annotations

from pathlib import Path

from core.checks.no_cloud_sdk import scan


AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"


def test_agent_code_has_no_cloud_sdk_or_direct_model_imports() -> None:
    assert scan(AGENT_DIR) == []


def test_agent_code_has_no_external_write_or_research_clients() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in AGENT_DIR.rglob("*.py")).lower()
    forbidden = ("google.cloud", "vertexai", "boto3", "botocore", "azure.", "litellm", "requests.", "httpx.", "optimizely", "vwo", "selenium", "playwright", ".publish(", ".send(", ".upload(")
    assert not any(token in text for token in forbidden)
