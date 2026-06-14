"""Agent 02 test import bootstrap.

The platform currently keeps each agent as a top-level ``agent`` package. Agent
01 remains the global pytest path because it is the reference agent, so Agent 02
tests put their own agent root first and clear any previously imported top-level
``agent`` module from another agent.
"""
from __future__ import annotations

import sys
from pathlib import Path


AGENT_ROOT = Path(__file__).resolve().parents[1]
root_str = str(AGENT_ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
else:
    sys.path.remove(root_str)
    sys.path.insert(0, root_str)

loaded = sys.modules.get("agent")
if loaded is not None:
    loaded_file = getattr(loaded, "__file__", "") or ""
    if root_str not in loaded_file:
        for name in list(sys.modules):
            if name == "agent" or name.startswith("agent."):
                del sys.modules[name]
