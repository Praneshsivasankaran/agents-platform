"""No-cloud-SDK import guard (AST-based) — agnostic-drift defense (DESIGN §4, §12; ADR-0003).

Scans ONLY agent business logic (``agents/*/agent/``) and fails if it imports a cloud SDK or a
direct STT SDK. Agent logic must reach clouds exclusively through ``core`` abstractions.

**Scope (important):** this guard scans only paths that are inside an ``agents/*/agent/``
directory. It deliberately does **not** scan ``packages/core/providers/{gcp,bedrock,azure}`` —
those provider implementations are *allowed* to import cloud SDKs. Explicit targets outside the
``agents/*/agent/`` scope are rejected with exit 1; relative imports are ignored.

**Fail-closed policy:**
- Explicit target does not exist → exit 1.
- Explicit target is outside ``agents/*/agent/`` scope → exit 1.
- Auto-discovery finds no ``agents/*/agent`` directories → exit 1.
- Any scanned file contains a SyntaxError → exit 1 (cannot guarantee cleanliness).
- All policies are tested in ``test_no_cloud_sdk.py``.

**Bypass prevention:** both ``import X`` and ``from X import Y`` are checked. The latter includes
``from google import cloud`` (module="google", name="cloud" → fqn "google.cloud" is banned), which
a module-only check would miss.

Usage:
    python -m core.checks.no_cloud_sdk          # auto-discovers agents/*/agent under cwd
    python -m core.checks.no_cloud_sdk PATH ...  # explicit agent-scope paths
Exit code 1 on any violation, missing path, out-of-scope path, no agent dirs, or parse error.
"""

from __future__ import annotations

import ast
import pathlib
import sys

# Cloud SDK roots + direct STT/LLM SDKs forbidden inside agent logic. Notes:
#   google.cloud.speech ⊆ google.cloud  ✓ (covered by "google.cloud")
#   azure.cognitiveservices.speech ⊆ azure  ✓ (covered by "azure")
#   google.api_core is the gRPC transport layer used by cloud SDKs — banned.
#   amazon_transcribe is the standalone async transcribe client (separate from boto3/botocore).
#   google.genai / google.generativeai are the modern Gemini SDKs — NOT subprefixes of
#     google.cloud, so they must be listed explicitly.
#   litellm/openai/anthropic/cohere are model SDKs: agent logic must call models through the
#     core LLMProvider abstraction, never a model SDK directly (DESIGN §4; AGENTS.md).
BANNED_PREFIXES = (
    # Cloud platform SDKs
    "google.cloud",
    "google.api_core",
    "google.genai",
    "google.generativeai",
    "google.auth",          # GCP credential SDK — auth belongs in providers, not agent logic
    "google.oauth2",        # GCP OAuth2 credentials
    "googleapiclient",      # google-api-python-client (Discovery API clients)
    "vertexai",
    "boto3",
    "botocore",
    "azure",
    # Direct STT SDKs
    "whisper",
    "faster_whisper",
    "deepgram",
    "assemblyai",
    "speech_recognition",
    "amazon_transcribe",
    # Direct LLM/model SDKs (must go through core.LLMProvider)
    "litellm",
    "openai",
    "anthropic",
    "cohere",
)


def _is_banned(module: str) -> bool:
    return any(module == b or module.startswith(b + ".") for b in BANNED_PREFIXES)


def _in_agent_scope(path: pathlib.Path) -> bool:
    """Return True if *path* is or is inside an ``agents/*/agent/`` directory.

    Walks up the path hierarchy looking for an ancestor whose name is ``"agent"`` and whose
    grandparent's name is ``"agents"``.  This is the only accepted target scope — provider
    implementation directories are explicitly excluded.
    """
    p = path.resolve() if path.exists() else path.absolute()
    while p != p.parent:
        if p.name == "agent" and p.parent.parent.name == "agents":
            return True
        p = p.parent
    return False


def _collect_importlib_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Return ``(module_aliases, func_aliases)`` for resolving dynamic-import calls.

    ``module_aliases`` — names bound to the ``importlib`` *module*::

        import importlib                 → {"importlib"}
        import importlib as il           → {"il"}
        import importlib.util            → {"importlib"}
        il2 = importlib                  → {"importlib", "il2"}

    ``func_aliases`` — names bound to ``importlib.import_module`` *itself*::

        from importlib import import_module          → {"import_module"}
        from importlib import import_module as im     → {"im"}
        im2 = importlib.import_module                 → {"im2"}
        im3 = im2                                     → {"im2", "im3"}

    Tracking real bindings is what distinguishes a genuine ``importlib.import_module`` call from
    (a) a locally-defined function named ``import_module`` — a false positive the old check
    produced — and from (b) ``obj.import_module(...)`` method calls on unrelated objects.  It
    also catches the assignment-alias bypass ``im = importlib.import_module; im("boto3")`` that
    the old check missed.  Assignment aliases are resolved to a fixed point so chains
    (``a = importlib.import_module; b = a``) are fully tracked.
    """
    module_aliases: set[str] = set()
    func_aliases: set[str] = set()

    # Import-based bindings.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # import importlib  /  import importlib as il  /  import importlib.util
                if alias.name == "importlib" or alias.name.startswith("importlib."):
                    module_aliases.add(alias.asname if alias.asname else "importlib")
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib" and node.level == 0:
            for alias in node.names:
                if alias.name == "import_module":
                    func_aliases.add(alias.asname if alias.asname else alias.name)

    # Assignment-based bindings — fixed point (handles alias chains, any statement order).
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            v = node.value
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not targets:
                continue
            # x = importlib            → x is a module alias
            if isinstance(v, ast.Name) and v.id in module_aliases:
                for t in targets:
                    if t not in module_aliases:
                        module_aliases.add(t)
                        changed = True
            # x = importlib.import_module   → x is a function alias
            elif (
                isinstance(v, ast.Attribute)
                and v.attr == "import_module"
                and isinstance(v.value, ast.Name)
                and v.value.id in module_aliases
            ):
                for t in targets:
                    if t not in func_aliases:
                        func_aliases.add(t)
                        changed = True
            # x = im   (im already a function alias)   → x is also a function alias
            elif isinstance(v, ast.Name) and v.id in func_aliases:
                for t in targets:
                    if t not in func_aliases:
                        func_aliases.add(t)
                        changed = True

    return module_aliases, func_aliases


def scan_file(path: pathlib.Path) -> list[tuple[str, int, str]]:
    """Return (file, lineno, module) triples for every banned import in *path*.

    Raises ``RuntimeError`` if the file cannot be parsed (SyntaxError) — a file that cannot be
    analysed cannot be certified clean (fail-closed).

    Two passes:

    Pass 1 (``_collect_importlib_aliases``): resolve which names actually refer to the
    ``importlib`` module and to ``importlib.import_module``, including ``import ... as`` and
    assignment-alias chains.  Pass 2 uses these so it flags real importlib calls only — not
    a local ``def import_module`` and not ``obj.import_module(...)`` on unrelated objects.

    Pass 2: detect banned static imports, ``from google import cloud`` fqn bypasses, resolved
    importlib calls, and ``__import__`` builtins (string-literal arguments only — variable
    arguments cannot be resolved statically).
    """
    bad: list[tuple[str, int, str]] = []
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"no_cloud_sdk: cannot read {path}: {e}") from e
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        # Fail closed: unparseable agent code cannot be verified; treat as a hard error.
        raise RuntimeError(
            f"no_cloud_sdk: cannot parse {path} (line {e.lineno}): {e.msg}"
        ) from e

    # ── Pass 1: resolve importlib module + function aliases ──────────────────
    module_aliases, func_aliases = _collect_importlib_aliases(tree)

    # ── Pass 2: detect violations ────────────────────────────────────────────
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # import X[, Y, ...]
            for alias in node.names:
                if _is_banned(alias.name):
                    bad.append((str(path), node.lineno, alias.name))

        elif isinstance(node, ast.ImportFrom):
            # Relative imports (from . / ..) can never be a top-level cloud SDK.
            if node.level > 0:
                continue
            if not node.module:
                continue
            # Check the module itself: "from google.cloud import speech" → caught.
            if _is_banned(node.module):
                bad.append((str(path), node.lineno, node.module))
                continue
            # Check each fully-qualified "module.name":
            # "from google import cloud" → module="google" (not banned), fqn="google.cloud" IS.
            for alias in node.names:
                fqn = f"{node.module}.{alias.name}"
                if _is_banned(fqn):
                    bad.append((str(path), node.lineno, fqn))

        elif isinstance(node, ast.Call):
            # Detect dynamic imports: importlib.import_module("boto3") and __import__("boto3").
            # These are escape hatches that bypass the static-import checks above.
            # Note: highly dynamic forms (e.g. importlib.import_module(var)) cannot be caught
            # statically; this check covers string-literal argument forms only.
            func = node.func

            # Resolve the module-name argument — try positional first, then the
            # keyword ``name=`` form: importlib.import_module(name="boto3").
            mod_arg: ast.expr | None = node.args[0] if node.args else None
            if mod_arg is None:
                for kw in node.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        mod_arg = kw.value
                        break

            if not (isinstance(mod_arg, ast.Constant) and isinstance(mod_arg.value, str)):
                continue
            mod_name: str = mod_arg.value
            if not _is_banned(mod_name):
                continue

            # Resolved importlib call forms (alias-aware — see _collect_importlib_aliases):
            #   <modalias>.import_module("x")   — ast.Attribute, value is a tracked module alias
            #                                       (so obj.import_module(...) is NOT flagged)
            #   <funcalias>("x")                — ast.Name whose id is a tracked function alias
            #                                       (so a local def import_module is NOT flagged)
            is_importlib = (
                (
                    isinstance(func, ast.Attribute)
                    and func.attr == "import_module"
                    and isinstance(func.value, ast.Name)
                    and func.value.id in module_aliases
                )
                or (isinstance(func, ast.Name) and func.id in func_aliases)
            )
            is_builtin = isinstance(func, ast.Name) and func.id == "__import__"
            if is_importlib:
                bad.append((str(path), node.lineno, f"importlib:{mod_name}"))
            elif is_builtin:
                bad.append((str(path), node.lineno, f"__import__:{mod_name}"))
    return bad


def scan(root: str | pathlib.Path) -> list[tuple[str, int, str]]:
    """Recursively scan all .py files under *root* (or *root* itself if it is a file).

    Raises ``RuntimeError`` on any SyntaxError (fail-closed; propagates to ``main``).
    """
    root = pathlib.Path(root)
    if root.is_file():
        return scan_file(root)
    bad: list[tuple[str, int, str]] = []
    for p in sorted(root.rglob("*.py")):
        bad.extend(scan_file(p))  # RuntimeError propagates
    return bad


def find_agent_dirs(repo_root: str | pathlib.Path) -> list[pathlib.Path]:
    """All ``agents/*/agent`` directories under *repo_root* (the only paths in scope).

    ``packages/core/providers/*`` is deliberately excluded — those may legitimately import cloud
    SDKs.  The guard never discovers them via auto-discovery, and explicit paths in that tree are
    rejected by ``main``.
    """
    return sorted((pathlib.Path(repo_root) / "agents").glob("*/agent"))


def main(argv: list[str]) -> int:
    """Entry point for ``python -m core.checks.no_cloud_sdk [PATH ...]``."""
    if argv:
        targets = [pathlib.Path(a) for a in argv]

        # Fail closed: any explicitly-supplied path that does not exist is an error.
        missing = [t for t in targets if not t.exists()]
        if missing:
            for t in missing:
                print(f"no_cloud_sdk: ERROR — target does not exist: {t}", file=sys.stderr)
            return 1

        # Scope enforcement: explicit targets must be inside agents/*/agent/.
        # This prevents accidentally scanning packages/core/providers/* which legitimately
        # imports cloud SDKs — scanning those dirs would produce false violations.
        out_of_scope = [t for t in targets if not _in_agent_scope(t)]
        if out_of_scope:
            for t in out_of_scope:
                print(
                    f"no_cloud_sdk: ERROR — target is outside agents/*/agent/ scope "
                    f"(provider dirs are excluded by design): {t}",
                    file=sys.stderr,
                )
            return 1
    else:
        targets = find_agent_dirs(pathlib.Path.cwd())
        # Fail closed: no agent dirs discovered is a configuration error, not a silent pass.
        if not targets:
            print(
                "no_cloud_sdk: FAIL — no agents/*/agent/ directories discovered under "
                f"{pathlib.Path.cwd()}. Run from the repo root or pass explicit paths.",
                file=sys.stderr,
            )
            return 1

    scanned: list[str] = []
    violations: list[tuple[str, int, str]] = []
    try:
        for t in targets:
            scanned.append(str(t))
            violations.extend(scan(t))
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    for f, line, mod in violations:
        print(f"FORBIDDEN cloud/STT SDK import in agent logic: {f}:{line} -> {mod}")
    if violations:
        print(f"no_cloud_sdk: FAIL — {len(violations)} violation(s)")
        return 1
    print(f"no_cloud_sdk: OK (scanned: {', '.join(scanned)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
