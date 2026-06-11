"""InMemoryObjectStorage — dict-backed ``ObjectStorage`` for dev/CI (no cloud, no disk).

NOT agent logic. Cloud-neutral.
"""

from __future__ import annotations

from ...interfaces import ObjectStorage


class InMemoryObjectStorage(ObjectStorage):
    name = "memory"

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> str:
        self._store[key] = bytes(data)
        return key

    def get(self, key: str) -> bytes:
        try:
            return self._store[key]
        except KeyError:
            raise KeyError(f"object not found: {key}") from None

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
