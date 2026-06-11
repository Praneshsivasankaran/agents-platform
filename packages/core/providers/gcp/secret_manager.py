"""GCP Secret Manager implementation of ``SecretStore``.

Production credential resolution: provider API keys / bucket names / project IDs are stored as
Secret Manager secrets and fetched at runtime. Same interface as ``EnvSecretStore`` — selected by
config (``secret_store.provider: gcp_secret_manager``), so swapping env → Secret Manager is a
config flip, not an agent change.

All ``google.cloud.secretmanager`` imports are confined to this module and are LAZY (deferred to
first ``get()``), so importing/constructing the store pulls in no cloud SDK — offline CI stays
keyless and SDK-free. Agent logic never imports this; it sees only the ``SecretStore`` interface.
"""

from __future__ import annotations

import os
import re
from typing import Any

from ...interfaces import SecretStore

# Secret IDs must match GCP's allowed pattern: letters, digits, hyphens, underscores (1-255).
_SECRET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,255}$")


class GCPSecretManagerSecretStore(SecretStore):
    """Resolve secrets from Google Cloud Secret Manager.

    Config (``cfg.secret_store``):
      - ``project`` (optional): GCP project hosting the secrets. Falls back to
        ``GOOGLE_CLOUD_PROJECT`` / ``GCP_PROJECT`` env at ``get()`` time. If unresolved, ``get()``
        raises a clear error rather than guessing.
      - ``prefix`` (optional): prepended to every requested key to form the secret id
        (e.g. prefix ``agent01-`` + key ``VERTEX_AI_PROJECT`` → secret ``agent01-VERTEX_AI_PROJECT``).
      - ``version`` (optional): secret version to access (default ``"latest"``).

    A missing secret returns ``None`` (same contract as ``EnvSecretStore``). Auth/permission and
    other errors PROPAGATE — they must not be mistaken for "secret absent" (fail closed).
    """

    name = "gcp_secret_manager"

    def __init__(self, cfg: dict[str, Any] | None = None, **_: Any) -> None:
        cfg = cfg or {}
        scfg = cfg.get("secret_store") or {}
        if not isinstance(scfg, dict):
            raise ValueError("cfg.secret_store must be a mapping")
        project = scfg.get("project", "")
        self._configured_project: str | None = project.strip() if isinstance(project, str) and project.strip() else None
        prefix = scfg.get("prefix", "")
        self._prefix: str = prefix if isinstance(prefix, str) else ""
        version = scfg.get("version", "latest")
        self._version: str = str(version).strip() or "latest"
        self._client = None  # lazy

    def _resolve_project(self) -> str:
        project = (
            self._configured_project
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("GCP_PROJECT")
        )
        if not project or not project.strip():
            raise ValueError(
                "GCPSecretManagerSecretStore: project is not configured — set "
                "cfg.secret_store.project or the GOOGLE_CLOUD_PROJECT env var"
            )
        return project.strip()

    def _get_client(self):
        if self._client is None:
            # Lazy import — keeps offline CI free of the cloud SDK until a secret is fetched.
            from google.cloud import secretmanager  # type: ignore[import-untyped]

            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def _secret_id(self, key: str) -> str:
        secret_id = f"{self._prefix}{key}"
        if not _SECRET_ID_RE.match(secret_id):
            raise ValueError(
                "GCPSecretManagerSecretStore: resolved secret id contains characters not "
                "permitted by Secret Manager (letters, digits, '-', '_' only)"
            )
        return secret_id

    def get(self, key: str) -> str | None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("GCPSecretManagerSecretStore: key must be a non-empty string")
        project = self._resolve_project()
        secret_id = self._secret_id(key)
        name = f"projects/{project}/secrets/{secret_id}/versions/{self._version}"
        client = self._get_client()
        try:
            response = client.access_secret_version(name=name)
        except Exception as exc:  # noqa: BLE001 — narrow to NotFound below, re-raise the rest
            if _is_not_found(exc):
                return None  # secret genuinely absent → same contract as EnvSecretStore
            raise  # auth/permission/transport errors must NOT look like "absent"
        return response.payload.data.decode("utf-8")


def _is_not_found(exc: Exception) -> bool:
    """True iff ``exc`` is a Secret-Manager 'secret/version does not exist' error.

    Tries the typed ``google.api_core.exceptions.NotFound`` first; falls back to the exception's
    class name so this stays importable and testable without google-api-core present.
    """
    try:
        from google.api_core import exceptions as gexc  # type: ignore[import-untyped]

        if isinstance(exc, gexc.NotFound):
            return True
    except Exception:  # noqa: BLE001 — SDK not installed (offline); fall back to name check
        pass
    return type(exc).__name__ == "NotFound"
