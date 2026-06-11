# core/checks

Home of `no_cloud_sdk.py` — the **no-cloud-SDK import guard** (DESIGN §4, §12; ADR-0003).

## What it does

AST-based scanner that inspects every `.py` file inside `agents/*/agent/` and fails if any file
imports a banned cloud SDK or direct STT SDK. Agent logic must reach clouds only through `core`
abstractions; cloud SDKs are permitted **only** in `packages/core/providers/{gcp,bedrock,azure}/`.

## Banned imports

Cloud platform SDKs: `google.cloud`, `google.api_core`, `google.genai`, `google.generativeai`,
`vertexai`, `boto3`, `botocore`, `azure`.
Google auth/credential SDKs: `google.auth`, `google.oauth2`, `googleapiclient`.
Direct STT SDKs: `whisper`, `faster_whisper`, `deepgram`, `assemblyai`, `speech_recognition`,
`amazon_transcribe`.
Direct model/LLM SDKs (agent logic must call models through `core.LLMProvider`, never these):
`litellm`, `openai`, `anthropic`, `cohere`.

Notes:
- `google.genai` and `google.generativeai` (modern Gemini SDKs) are **not** subprefixes of
  `google.cloud`, so they are listed explicitly.
- `google.auth` / `google.oauth2` / `googleapiclient` are the GCP credential and Discovery
  API client SDKs — auth and direct API clients belong in `providers/`, not agent logic.
- `google.protobuf` is **not** banned (protobuf is a generic serialization library).

Both `import X` and `from X import Y` forms are detected, including the `from google import cloud`
bypass (fqn check: module + alias name).

Dynamic import forms are also detected (string-literal argument only; variable forms are
undetectable statically). The guard first resolves which names actually refer to the `importlib`
module and to `importlib.import_module` (via `_collect_importlib_aliases`), then flags only real
importlib calls:
- `importlib.import_module("boto3")` — attribute call form
- `importlib.import_module(name="boto3")` — keyword-argument form
- `import importlib as il; il.import_module("boto3")` — aliased-module form
- `from importlib import import_module [as im]; im("boto3")` — function-import form
- `im = importlib.import_module; im("boto3")` — assignment-alias form (resolved to a fixed
  point, so alias chains `a = importlib.import_module; b = a; b(...)` are caught)
- `__import__("boto3")` — builtin form

Resolving real bindings avoids two false positives a naive name/attribute check produces:
a locally-defined `def import_module(...)`, and `obj.import_module(...)` method calls on objects
unrelated to importlib. Neither is bound to importlib, so neither is flagged.

## Fail-closed policies

- Explicit target does not exist → exit 1.
- Explicit target is **outside `agents/*/agent/` scope** → exit 1 (provider dirs are excluded by
  design; scanning them would produce false violations).
- Auto-discovery finds no `agents/*/agent/` dirs → exit 1.
- Any scanned file has a `SyntaxError` → exit 1 (cannot certify cleanliness).

## Usage

```
# Auto-discovers all agents/*/agent/ dirs under cwd (used in CI):
PYTHONPATH=packages python -m core.checks.no_cloud_sdk

# Explicit paths (must be inside agents/*/agent/):
PYTHONPATH=packages python -m core.checks.no_cloud_sdk agents/agent-01-blog-writer/agent
```

## CI wiring

The guard is step 1 in `.github/workflows/ci.yaml` (after static compile, before import smoke and
tests). It uses auto-discovery so new agents are covered with zero CI change. Non-zero exit fails
the build.

## Tests

`packages/core/tests/test_no_cloud_sdk.py` covers all banned prefixes (both import forms,
including the modern Gemini and direct-model SDKs), the `from google import cloud` bypass,
clean/relative imports, scope discovery/exclusion, explicit provider-path rejection, missing
targets, no-discovery fail-closed, SyntaxError fail-closed, and multi-agent auto-discovery
coverage. Dynamic-import coverage includes the aliased-module, function-import, keyword-arg,
assignment-alias, and chained-alias forms, plus the two false-positive guards (a locally-defined
`import_module` function and `obj.import_module(...)` on unrelated objects).
