"""Test harness for realm-of-agents.

The service runs as FLAT modules (config, roster, cards, roles, …) that import each other by bare name
(`from config import ...`), with the service dir on the path — not as a package. So put that dir on
``sys.path`` here and the unit tests import the modules exactly as the running service does.

Scope: these tests cover the PURE-LOGIC modules — the roster (the single-source agent list), the A2A card
builders, and the config/roles data — which need no runtime deps. The framework modules (app.py, a2a.py,
agents.py, stream.py) pull FastAPI + the a2a SDK + httpx and are validated live, not here.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
