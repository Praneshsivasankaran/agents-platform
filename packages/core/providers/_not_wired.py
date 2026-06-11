"""Shared helper for interface-complete provider stubs (DESIGN §4.2, §12).

Bedrock + Azure providers are *interface-complete stubs* in v1: every class subclasses
its ``core.interfaces`` ABC and is instantiable, so the agent and factory cannot tell a
stub from a wired backend at construction time. Only the method *bodies* are empty — and
they fail **loudly** (``NotImplementedError``) rather than silently returning, so a missing
backend can never masquerade as a passing one. Going live is "fill the body + flip the
config", never a redesign.

This module imports only the standard library — never a cloud SDK.
"""

from __future__ import annotations


def not_wired(cloud: str, service: str, method: str) -> NotImplementedError:
    """Build the canonical loud error for an unfilled stub method.

    ``cloud`` is the human cloud name (e.g. ``"AWS"``), ``service`` the concrete backend
    (e.g. ``"Bedrock LLM"``), ``method`` the interface method that was called.
    """
    return NotImplementedError(
        f"{cloud} {service}: '{method}' is a v1 interface-complete stub and is not wired yet. "
        f"The interface is fully satisfied (isinstance + signatures); fill this method body "
        f"and select this backend via config to go live (DESIGN §4.2/§12, ADR-0001)."
    )
