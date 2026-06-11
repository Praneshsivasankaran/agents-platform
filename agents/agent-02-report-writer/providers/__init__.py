"""Thin provider wiring for Report Writing Agent.

Backends are resolved through ``core.factory`` (config-driven); this package holds only
agent-specific wiring helpers, if any. NEVER import a cloud SDK here — that belongs in
``packages/core/providers/{gcp,bedrock,azure}``.
"""
