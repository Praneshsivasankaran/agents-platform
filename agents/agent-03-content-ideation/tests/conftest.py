"""Agent 03 test import bootstrap."""
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
