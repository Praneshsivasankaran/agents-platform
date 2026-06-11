"""ObjectStorage — blob seam for uploads (audio/video) and drafts (DESIGN §3, §10).

Agent logic passes storage *references* (keys) through graph state, never raw cloud
objects. Raw media has short/no retention (DESIGN §10) — deletion is part of the
contract. In-memory mock for tests; GCP impl first; AWS/Azure stubbed.

Cloud-neutral by construction: standard library only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ObjectStorage(ABC):
    """Abstract blob store. The only storage seam agent logic may import."""

    name: str = "base"

    @abstractmethod
    def put(self, key: str, data: bytes) -> str:
        """Store ``data`` under ``key``; return the stored reference (key)."""
        raise NotImplementedError

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Fetch the bytes stored under ``key``."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the blob under ``key`` (used to honor short-retention of raw media)."""
        raise NotImplementedError
