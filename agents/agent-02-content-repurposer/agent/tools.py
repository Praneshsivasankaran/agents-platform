"""Provider-neutral helper tools for Agent 02."""
from __future__ import annotations

import json

from core.interfaces import ObjectStorage, Telemetry

from .schemas import RepurposedContentPackage


def best_effort_store_package(
    *,
    storage: ObjectStorage | None,
    tel: Telemetry,
    package: RepurposedContentPackage,
    prefix: str,
) -> str | None:
    """Store the final package through ObjectStorage when available.

    Storage failure must not block local/test mode because the package is returned
    inline. Errors are logged as metadata only; raw package content is not logged.
    """
    if storage is None:
        return None
    package_id = package.package_id or "agent02-package"
    key = f"{prefix.rstrip('/')}/{package_id}.json"
    payload = json.dumps(package.model_dump(mode="json"), ensure_ascii=True, indent=2).encode("utf-8")
    try:
        stored = storage.put(key, payload)
    except Exception as exc:  # noqa: BLE001
        try:
            tel.log("output_storage.error", kind=type(exc).__name__)
        except Exception:
            pass
        return None
    try:
        tel.log("output_storage.complete")
    except Exception:
        pass
    return stored or key
