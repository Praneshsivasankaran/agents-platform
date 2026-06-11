"""Azure Blob Storage ObjectStorage — interface-complete stub (v1; not wired).

Satisfies the ``ObjectStorage`` ABC. ``put``/``get``/``delete`` raise ``NotImplementedError``
loudly. When filled in, ``azure.storage.blob`` is imported lazily here — never in agent logic.
"""

from __future__ import annotations

from typing import Any

from ...interfaces.object_storage import ObjectStorage
from .._not_wired import not_wired


class AzureObjectStorage(ObjectStorage):
    """Azure Blob Storage blob backend (stub). Instantiable; every operation fails loudly."""

    name = "azure_blob"

    def __init__(self, cfg: dict[str, Any] | None = None, *, secret_store=None, **_: Any) -> None:
        self._cfg = cfg or {}
        self._secret_store = secret_store

    def put(self, key: str, data: bytes) -> str:
        raise not_wired("Azure", "Blob Storage", "put")

    def get(self, key: str) -> bytes:
        raise not_wired("Azure", "Blob Storage", "get")

    def delete(self, key: str) -> None:
        raise not_wired("Azure", "Blob Storage", "delete")
