"""Offline tests for the GCP Secret Manager SecretStore using a stubbed SDK.

Per DESIGN §10: secrets are fetched at runtime through the SecretStore seam, never embedded.
This provider must (a) satisfy the SecretStore interface, (b) defer the cloud SDK import until a
secret is actually fetched (offline-safe), (c) return None for a genuinely-absent secret but
PROPAGATE auth/permission errors (fail closed — absent != denied), and (d) be selectable by the
factory via config.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.interfaces import SecretStore
from core.providers.gcp.secret_manager import GCPSecretManagerSecretStore


# ---------------------------------------------------------------------------
# Fake google.cloud.secretmanager + google.api_core.exceptions
# ---------------------------------------------------------------------------

class _FakeNotFound(Exception):
    """Stand-in named exactly 'NotFound' so the name-based fallback also recognizes it."""


_FakeNotFound.__name__ = "NotFound"


def _secretmanager_modules(*, payload: bytes | None = None, side_effect=None):
    client = MagicMock()
    if side_effect is not None:
        client.access_secret_version.side_effect = side_effect
    else:
        client.access_secret_version.return_value = SimpleNamespace(
            payload=SimpleNamespace(data=payload)
        )

    secretmanager = types.ModuleType("google.cloud.secretmanager")
    secretmanager.SecretManagerServiceClient = lambda: client

    api_core = types.ModuleType("google.api_core")
    exceptions = types.ModuleType("google.api_core.exceptions")
    exceptions.NotFound = _FakeNotFound
    api_core.exceptions = exceptions

    cloud = types.ModuleType("google.cloud")
    cloud.secretmanager = secretmanager
    google = types.ModuleType("google")
    google.cloud = cloud
    google.api_core = api_core

    modules = {
        "google": google,
        "google.cloud": cloud,
        "google.cloud.secretmanager": secretmanager,
        "google.api_core": api_core,
        "google.api_core.exceptions": exceptions,
    }
    return client, modules


def _cfg(**secret_store):
    base = {"provider": "gcp_secret_manager", "project": "proj-123"}
    base.update(secret_store)
    return {"secret_store": base}


# ---------------------------------------------------------------------------
# Interface + offline-safety
# ---------------------------------------------------------------------------

def test_is_secret_store_and_named():
    store = GCPSecretManagerSecretStore(_cfg())
    assert isinstance(store, SecretStore)
    assert store.name == "gcp_secret_manager"


def test_construction_imports_no_cloud_sdk():
    """Constructing the store must NOT import google.cloud.secretmanager (lazy import)."""
    # Make sure a prior test didn't leave it loaded by our own faking.
    for mod in ("google.cloud.secretmanager",):
        sys.modules.pop(mod, None)
    GCPSecretManagerSecretStore(_cfg())
    assert "google.cloud.secretmanager" not in sys.modules, (
        "SecretStore construction must defer the cloud SDK import until get()"
    )


# ---------------------------------------------------------------------------
# get() behavior
# ---------------------------------------------------------------------------

def test_get_returns_decoded_payload():
    client, modules = _secretmanager_modules(payload=b"super-secret-value")
    store = GCPSecretManagerSecretStore(_cfg())
    with patch.dict(sys.modules, modules):
        value = store.get("VERTEX_AI_PROJECT")
    assert value == "super-secret-value"
    name = client.access_secret_version.call_args.kwargs["name"]
    assert name == "projects/proj-123/secrets/VERTEX_AI_PROJECT/versions/latest"


def test_prefix_and_version_are_applied():
    client, modules = _secretmanager_modules(payload=b"v")
    store = GCPSecretManagerSecretStore(_cfg(prefix="agent01-", version="3"))
    with patch.dict(sys.modules, modules):
        store.get("API_KEY")
    name = client.access_secret_version.call_args.kwargs["name"]
    assert name == "projects/proj-123/secrets/agent01-API_KEY/versions/3"


def test_missing_secret_returns_none():
    _, modules = _secretmanager_modules(side_effect=_FakeNotFound("nope"))
    store = GCPSecretManagerSecretStore(_cfg())
    with patch.dict(sys.modules, modules):
        assert store.get("DOES_NOT_EXIST") is None


def test_auth_error_propagates_not_swallowed_as_absent():
    """A permission/auth error must NOT be mistaken for 'secret absent' (fail closed)."""
    class PermissionDenied(Exception):
        pass

    _, modules = _secretmanager_modules(side_effect=PermissionDenied("403"))
    store = GCPSecretManagerSecretStore(_cfg())
    with patch.dict(sys.modules, modules):
        with pytest.raises(PermissionDenied):
            store.get("VERTEX_AI_PROJECT")


def test_project_resolves_from_env_when_not_configured(monkeypatch):
    client, modules = _secretmanager_modules(payload=b"x")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-proj")
    store = GCPSecretManagerSecretStore({"secret_store": {"provider": "gcp_secret_manager"}})
    with patch.dict(sys.modules, modules):
        store.get("KEY")
    name = client.access_secret_version.call_args.kwargs["name"]
    assert name.startswith("projects/env-proj/secrets/")


def test_unresolvable_project_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    store = GCPSecretManagerSecretStore({"secret_store": {"provider": "gcp_secret_manager"}})
    with pytest.raises(ValueError, match="project is not configured"):
        store.get("KEY")


def test_blank_key_rejected():
    store = GCPSecretManagerSecretStore(_cfg())
    with pytest.raises(ValueError, match="non-empty string"):
        store.get("   ")


def test_invalid_secret_id_rejected():
    store = GCPSecretManagerSecretStore(_cfg())
    with pytest.raises(ValueError, match="not permitted"):
        store.get("bad key/with slash")


# ---------------------------------------------------------------------------
# Factory selection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", ["gcp", "gcp_secret_manager", "secretmanager"])
def test_factory_selects_secret_manager(provider):
    from core.factory import get_secret_store

    store = get_secret_store({"secret_store": {"provider": provider, "project": "p"}})
    assert isinstance(store, GCPSecretManagerSecretStore)


def test_factory_still_defaults_to_env():
    from core.factory import get_secret_store
    from core.providers.mock import EnvSecretStore

    assert isinstance(get_secret_store({}), EnvSecretStore)
    assert isinstance(get_secret_store({"secret_store": {"provider": "env"}}), EnvSecretStore)
