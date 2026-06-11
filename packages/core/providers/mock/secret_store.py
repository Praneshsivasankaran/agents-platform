"""EnvSecretStore — environment-variable-backed ``SecretStore`` for dev/CI.

The offline/keyless default: secrets come from ``os.environ`` (never from code/images). Cloud
secret managers (GCP Secret Manager / AWS Secrets Manager / Azure Key Vault) implement the same
interface later, in their provider packages. NOT agent logic. Cloud-neutral.
"""

from __future__ import annotations

import os

from ...interfaces import SecretStore


class EnvSecretStore(SecretStore):
    name = "env"

    def get(self, key: str) -> str | None:
        return os.environ.get(key)
