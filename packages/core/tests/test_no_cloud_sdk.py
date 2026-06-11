"""Tests for the no-cloud-SDK import guard: detection, bypasses, fail-closed, and scope.

Covers:
- All banned prefixes detected via both ``import X`` and ``from X import Y`` forms.
- The ``from google import cloud`` bypass (fqn check) that a module-only guard misses.
- Direct STT SDKs including ``amazon_transcribe``.
- Clean/relative imports pass.
- Scope: only ``agents/*/agent/`` discovered, never ``packages/core/providers/*``.
- Scope enforcement for explicit paths: provider dirs → exit 1.
- Fail-closed: missing target → exit 1; no agent dirs → exit 1; SyntaxError → exit 1.
- All-agent CI: auto-discovery covers multiple agents.
"""

from __future__ import annotations

import pytest

from core.checks import no_cloud_sdk as guard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mods(violations: list) -> set[str]:
    return {m for _, _, m in violations}


def _write(tmp_path, filename: str, code: str):
    f = tmp_path / filename
    f.write_text(code, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Detection: import X (ast.Import)
# ---------------------------------------------------------------------------


def test_flags_cloud_sdk_bare_imports(tmp_path):
    _write(tmp_path, "node.py",
           "import boto3\nimport vertexai\nimport botocore\nimport azure\n")
    mods = _mods(guard.scan(tmp_path))
    assert {"boto3", "vertexai", "botocore", "azure"} <= mods


def test_flags_cloud_sdk_dotted_bare_imports(tmp_path):
    _write(tmp_path, "node.py",
           "import google.cloud\nimport google.api_core\nimport azure.storage\n")
    mods = _mods(guard.scan(tmp_path))
    assert {"google.cloud", "google.api_core", "azure.storage"} <= mods


def test_flags_from_module_import(tmp_path):
    """from google.cloud import storage  — module IS banned, caught by module check."""
    _write(tmp_path, "node.py", "from google.cloud import storage\nfrom azure import something\n")
    mods = _mods(guard.scan(tmp_path))
    assert {"google.cloud", "azure"} <= mods


def test_flags_from_google_import_cloud_bypass(tmp_path):
    """BYPASS: from google import cloud — module='google' (not banned), but fqn='google.cloud' IS.

    A module-only check misses this; the guard must check module.name for each alias.
    """
    _write(tmp_path, "bypass.py", "from google import cloud\n")
    mods = _mods(guard.scan(tmp_path))
    assert "google.cloud" in mods, (
        "Guard must catch 'from google import cloud' via fqn check (module + alias name)"
    )


def test_flags_from_google_import_api_core_bypass(tmp_path):
    """BYPASS: from google import api_core — same pattern as google.cloud."""
    _write(tmp_path, "bypass2.py", "from google import api_core\n")
    mods = _mods(guard.scan(tmp_path))
    assert "google.api_core" in mods


# ---------------------------------------------------------------------------
# Detection: all banned prefixes (both import forms)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stmt,expected_mod", [
    ("import google.cloud", "google.cloud"),
    ("import google.api_core", "google.api_core"),
    ("import vertexai", "vertexai"),
    ("import boto3", "boto3"),
    ("import botocore", "botocore"),
    ("import azure", "azure"),
    ("import whisper", "whisper"),
    ("import faster_whisper", "faster_whisper"),
    ("import deepgram", "deepgram"),
    ("import assemblyai", "assemblyai"),
    ("import speech_recognition", "speech_recognition"),
    ("import amazon_transcribe", "amazon_transcribe"),
    ("from google import cloud", "google.cloud"),
    ("from google import api_core", "google.api_core"),
    ("from google.cloud import speech", "google.cloud"),
    ("from vertexai import language_models", "vertexai"),
    ("from boto3 import Session", "boto3"),
    ("from azure.storage import blob", "azure.storage"),
    # module="amazon_transcribe.client" starts with "amazon_transcribe." → banned;
    # violation records the actual module string (not the prefix).
    ("from amazon_transcribe.client import TranscribeStreamingClient", "amazon_transcribe.client"),
    # Modern Gemini SDKs — NOT subprefixes of google.cloud, listed explicitly.
    ("import google.genai", "google.genai"),
    ("from google import genai", "google.genai"),
    ("import google.generativeai", "google.generativeai"),
    ("from google import generativeai", "google.generativeai"),
    ("from google.generativeai import GenerativeModel", "google.generativeai"),
    # Direct model SDKs — agent logic must go through core.LLMProvider, never these.
    ("import litellm", "litellm"),
    ("from litellm import completion", "litellm"),
    ("import openai", "openai"),
    ("from openai import OpenAI", "openai"),
    ("import anthropic", "anthropic"),
    ("import cohere", "cohere"),
    # Google auth / API-client SDKs — auth + cloud clients belong in providers, not agent logic.
    ("import google.auth", "google.auth"),
    ("from google import auth", "google.auth"),
    ("from google.auth import default", "google.auth"),
    ("import google.oauth2", "google.oauth2"),
    ("from google.oauth2 import service_account", "google.oauth2"),
    ("import googleapiclient", "googleapiclient"),
    ("from googleapiclient.discovery import build", "googleapiclient.discovery"),
])
def test_every_banned_import(tmp_path, stmt, expected_mod):
    _write(tmp_path, "agent.py", stmt + "\n")
    mods = _mods(guard.scan(tmp_path))
    assert expected_mod in mods, f"Expected {expected_mod!r} to be flagged for: {stmt!r}"


# ---------------------------------------------------------------------------
# Detection: direct STT SDKs
# ---------------------------------------------------------------------------


def test_flags_direct_stt_sdks(tmp_path):
    _write(tmp_path, "stt.py",
           "import whisper\nimport deepgram\nimport speech_recognition\nimport amazon_transcribe\n")
    mods = _mods(guard.scan(tmp_path))
    assert {"whisper", "deepgram", "speech_recognition", "amazon_transcribe"} <= mods


# ---------------------------------------------------------------------------
# Clean-pass cases
# ---------------------------------------------------------------------------


def test_allows_clean_and_relative_imports(tmp_path):
    _write(tmp_path, "clean.py",
           "from core import LLMProvider\nfrom . import sibling\nimport json\nimport os\n")
    assert guard.scan(tmp_path) == []


def test_allows_non_banned_google_submodule(tmp_path):
    """'from google import protobuf' — 'google.protobuf' is not in BANNED_PREFIXES."""
    _write(tmp_path, "proto.py", "from google import protobuf\n")
    assert guard.scan(tmp_path) == []


# ---------------------------------------------------------------------------
# Scope: only agents/*/agent, never packages/core/providers/*
# ---------------------------------------------------------------------------


def test_scope_only_agent_dirs_not_providers(tmp_path):
    # A provider impl that legitimately imports a cloud SDK must NOT be discovered.
    gcp = tmp_path / "packages" / "core" / "providers" / "gcp"
    gcp.mkdir(parents=True)
    (gcp / "impl.py").write_text("import google.cloud\n", encoding="utf-8")
    agent_dir = tmp_path / "agents" / "agent-01-blog-writer" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "node.py").write_text("from core import LLMProvider\n", encoding="utf-8")

    discovered = guard.find_agent_dirs(tmp_path)
    assert discovered == [agent_dir]  # only agents/*/agent, never providers
    violations = []
    for d in discovered:
        violations += guard.scan(d)
    assert violations == []


def test_find_agent_dirs_discovers_multiple(tmp_path):
    """Auto-discovery returns all agents/*/agent dirs, not just the first."""
    for name in ("agent-01-foo", "agent-02-bar", "agent-03-baz"):
        d = tmp_path / "agents" / name / "agent"
        d.mkdir(parents=True)
    found = guard.find_agent_dirs(tmp_path)
    assert len(found) == 3
    for d in found:
        assert d.parent.parent.name == "agents"
        assert d.name == "agent"


# ---------------------------------------------------------------------------
# Scope enforcement: explicit provider-dir targets must be rejected
# ---------------------------------------------------------------------------


def test_explicit_provider_path_rejected(tmp_path):
    """Explicitly passing packages/core/providers/gcp must be rejected (not scanned).

    Provider dirs legitimately import cloud SDKs; scanning them would produce false violations
    AND would silently certify that a path outside the agent boundary is 'clean'.
    """
    provider_dir = tmp_path / "packages" / "core" / "providers" / "gcp"
    provider_dir.mkdir(parents=True)
    (provider_dir / "impl.py").write_text("import google.cloud\n", encoding="utf-8")
    result = guard.main([str(provider_dir)])
    assert result == 1, (
        "Guard must reject explicit targets outside agents/*/agent/ scope "
        "(provider dir was accepted — false scan boundary)"
    )


def test_explicit_agent_path_accepted(tmp_path):
    """An explicit path inside agents/*/agent/ must be accepted and scanned."""
    agent_dir = tmp_path / "agents" / "a1" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "ok.py").write_text("from core import LLMProvider\n", encoding="utf-8")
    assert guard.main([str(agent_dir)]) == 0


def test_in_agent_scope_helper(tmp_path):
    """_in_agent_scope correctly identifies agent vs provider paths."""
    agent_dir = tmp_path / "agents" / "a1" / "agent"
    agent_dir.mkdir(parents=True)
    provider_dir = tmp_path / "packages" / "core" / "providers" / "gcp"
    provider_dir.mkdir(parents=True)

    assert guard._in_agent_scope(agent_dir) is True
    assert guard._in_agent_scope(agent_dir / "node.py") is True
    assert guard._in_agent_scope(provider_dir) is False


# ---------------------------------------------------------------------------
# Fail-closed: exit codes
# ---------------------------------------------------------------------------


def test_main_returns_nonzero_on_violation(tmp_path):
    agent_dir = tmp_path / "agents" / "a1" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "leak.py").write_text("import boto3\n", encoding="utf-8")
    assert guard.main([str(agent_dir)]) == 1


def test_main_ok_on_clean(tmp_path):
    agent_dir = tmp_path / "agents" / "a1" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "ok.py").write_text("from core import LLMProvider\n", encoding="utf-8")
    assert guard.main([str(agent_dir)]) == 0


def test_main_fails_on_missing_explicit_path(tmp_path):
    """Explicit path that does not exist must return exit 1 (fail closed)."""
    missing = tmp_path / "does" / "not" / "exist"
    result = guard.main([str(missing)])
    assert result == 1, "Guard must fail closed when an explicit target path does not exist"


def test_main_fails_when_no_agent_dirs_discovered(tmp_path, monkeypatch):
    """Auto-discovery with no agents/*/agent dirs must return exit 1 (fail closed)."""
    monkeypatch.chdir(tmp_path)
    result = guard.main([])
    assert result == 1, "Guard must fail closed when auto-discovery finds no agent dirs"


def test_main_auto_discovery_covers_all_agents(tmp_path, monkeypatch):
    """CI using auto-discovery must scan every agent, not just the first one."""
    for name in ("agent-01-foo", "agent-02-bar"):
        d = tmp_path / "agents" / name / "agent"
        d.mkdir(parents=True)
        if name == "agent-02-bar":
            (d / "leak.py").write_text("import boto3\n", encoding="utf-8")
        else:
            (d / "ok.py").write_text("from core import LLMProvider\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert guard.main([]) == 1, "Auto-discovery must fail when ANY discovered agent has a violation"


def test_guard_detects_importlib_import_module(tmp_path):
    """Dynamic imports via importlib.import_module('boto3') must be caught."""
    _write(tmp_path, "dynamic.py",
           'import importlib\nm = importlib.import_module("boto3")\n')
    mods = _mods(guard.scan(tmp_path))
    assert any("boto3" in m for m in mods), (
        "importlib.import_module('boto3') must be detected as a banned dynamic import"
    )


def test_guard_detects_importlib_alias_form(tmp_path):
    """BYPASS: ``from importlib import import_module; import_module('boto3')`` must be caught.

    When ``import_module`` is imported as a bare name (``ast.Name``), the previous check only
    covered the ``ast.Attribute`` form (``importlib.import_module``).  The guard must also
    handle the alias import pattern where the function is called without the module prefix.
    """
    _write(tmp_path, "alias_dynamic.py",
           'from importlib import import_module\nm = import_module("boto3")\n')
    mods = _mods(guard.scan(tmp_path))
    assert any("boto3" in m for m in mods), (
        "from importlib import import_module; import_module('boto3') must be detected — "
        "alias form (ast.Name) must be caught in addition to the attribute form (ast.Attribute)"
    )


def test_guard_detects_builtin_import(tmp_path):
    """Dynamic imports via __import__('vertexai') must be caught."""
    _write(tmp_path, "builtin.py", '__import__("vertexai")\n')
    mods = _mods(guard.scan(tmp_path))
    assert any("vertexai" in m for m in mods), (
        "__import__('vertexai') must be detected as a banned dynamic import"
    )


def test_guard_detects_importlib_keyword_name_arg(tmp_path):
    """BYPASS: ``importlib.import_module(name='boto3')`` (keyword arg) must be caught.

    ``import_module`` accepts ``name`` as a keyword argument.  The previous check only
    resolved ``node.args[0]`` (positional), missing the ``name=`` keyword form entirely.
    """
    _write(tmp_path, "kwarg.py",
           'import importlib\nm = importlib.import_module(name="boto3")\n')
    mods = _mods(guard.scan(tmp_path))
    assert any("boto3" in m for m in mods), (
        "importlib.import_module(name='boto3') must be detected — keyword-arg bypass"
    )


def test_guard_does_not_flag_importlib_of_safe_module(tmp_path):
    """importlib.import_module of a non-banned module must not produce a violation."""
    _write(tmp_path, "safe.py", 'import importlib\nm = importlib.import_module("json")\n')
    assert guard.scan(tmp_path) == []


def test_guard_no_false_positive_for_local_import_module(tmp_path):
    """A locally-defined function named ``import_module`` must NOT be flagged.

    The guard resolves real importlib bindings (``_collect_importlib_aliases``) and only flags
    calls to names that genuinely refer to ``importlib.import_module``.  A locally-defined
    function with the same name is not bound to importlib, so it is not flagged.
    """
    _write(tmp_path, "local_fn.py",
           'def import_module(name: str) -> str:\n'
           '    return name\n'
           'result = import_module("boto3")\n')
    assert guard.scan(tmp_path) == [], (
        "A locally-defined import_module() function must not be flagged — "
        "only functions actually bound to importlib should trigger detection"
    )


def test_guard_no_false_positive_for_method_named_import_module(tmp_path):
    """``obj.import_module("boto3")`` on an unrelated object must NOT be flagged.

    Round 7 fix: the attribute form now requires the receiver to be a tracked importlib module
    alias.  A method call on an arbitrary object (``self``/``loader``/etc.) is not importlib and
    must not be a false positive.
    """
    _write(tmp_path, "method.py",
           'class Loader:\n'
           '    def import_module(self, name):\n'
           '        return name\n'
           'loader = Loader()\n'
           'loader.import_module("boto3")\n')
    assert guard.scan(tmp_path) == [], (
        "A method named import_module on an unrelated object must not be flagged"
    )


def test_guard_detects_importlib_module_as_alias(tmp_path):
    """``import importlib as il; il.import_module('boto3')`` must be caught (module aliased)."""
    _write(tmp_path, "modalias.py",
           'import importlib as il\nm = il.import_module("boto3")\n')
    mods = _mods(guard.scan(tmp_path))
    assert any("boto3" in m for m in mods), (
        "Aliased importlib module (import importlib as il) must still be detected"
    )


def test_guard_detects_assignment_alias_of_import_module(tmp_path):
    """BYPASS: ``im = importlib.import_module; im('boto3')`` must be caught.

    Round 7 fix: assignment aliases of the function object are now tracked to a fixed point,
    so binding ``importlib.import_module`` to a local name and calling it does not bypass.
    """
    _write(tmp_path, "assign_alias.py",
           'import importlib\nim = importlib.import_module\nm = im("boto3")\n')
    mods = _mods(guard.scan(tmp_path))
    assert any("boto3" in m for m in mods), (
        "Assignment alias of importlib.import_module must be detected (im = importlib.import_module)"
    )


def test_guard_detects_chained_assignment_alias(tmp_path):
    """A chained alias (``a = importlib.import_module; b = a; b('boto3')``) must be caught."""
    _write(tmp_path, "chain.py",
           'import importlib\na = importlib.import_module\nb = a\nm = b("boto3")\n')
    mods = _mods(guard.scan(tmp_path))
    assert any("boto3" in m for m in mods), "Chained assignment aliases must be tracked"


def test_syntax_error_in_scanned_file_fails_closed(tmp_path):
    """A SyntaxError in agent code must cause the guard to fail (not silently skip).

    A file that cannot be parsed cannot be certified clean — fail closed.
    """
    agent_dir = tmp_path / "agents" / "a1" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "broken.py").write_text("def foo(:\n    pass\n", encoding="utf-8")
    result = guard.main([str(agent_dir)])
    assert result == 1, "SyntaxError in agent code must be treated as a scan failure (fail closed)"
