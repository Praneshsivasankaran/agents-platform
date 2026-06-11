"""SecretStore — credentials seam (DESIGN §10).

Provider API keys / storage creds / STT keys are fetched here at runtime, never
embedded in code, images, config, or logs. ``EnvSecretStore`` (env-var backed) is the
offline default; GCP Secret Manager / AWS Secrets Manager / Azure Key Vault impls sit
behind this same interface.

Cloud-neutral by construction: standard library only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretStore(ABC):
    """Abstract secret store. The only credentials seam agent logic may import."""

    name: str = "base"

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Return the secret value for ``key``, or ``None`` if absent."""
        raise NotImplementedError
