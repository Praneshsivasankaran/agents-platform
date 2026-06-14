from __future__ import annotations

from pathlib import Path


AGENT_DIR = Path(__file__).resolve().parents[2] / "agent"


def _agent_python_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in AGENT_DIR.rglob("*.py"))


def test_agent_code_has_no_cloud_sdk_or_direct_model_imports() -> None:
    text = _agent_python_text()

    forbidden = (
        "google.cloud",
        "google.genai",
        "google.generativeai",
        "google.auth",
        "google.oauth2",
        "googleapiclient",
        "vertexai",
        "boto3",
        "botocore",
        "azure.",
        "openai",
        "anthropic",
        "cohere",
        "litellm",
    )
    assert not any(token in text for token in forbidden)


def test_agent_code_has_no_external_write_or_publishing_clients() -> None:
    text = _agent_python_text().lower()

    forbidden = (
        ".publish(",
        ".post(",
        ".schedule(",
        "cms",
        "crm",
        "facebook",
        "instagram graph api",
        "linkedin api",
        "twitter api",
        "x api",
        "mailchimp",
        "sendgrid",
        "requests.",
        "httpx.",
    )
    assert not any(token in text for token in forbidden)
