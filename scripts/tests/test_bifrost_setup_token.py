"""Guard (B202): every caller of Bifrost's management API sends the setup token.

From Bifrost v2.2.6, with dashboard auth off (the lab's setting), every non-public `/api` call needs the
`X-Bifrost-Setup-Token` header or it gets 401 — so a caller that forgets it breaks silently until it next runs (the
weekly registrations, a rebuild after a PVC loss). This finds every Python file that calls a Bifrost `/api` path in
code (a quoted path, not prose in a docstring) and asserts it reads BIFROST_SETUP_TOKEN and sends the header. The
caller list is DERIVED, so a new caller is covered the day it lands; an empty list fails (a guard that finds nothing
checks nothing). Runbook: docs/runbooks/mcp-gateway.md § Bifrost setup token.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = [REPO / "nodes", REPO / "scripts"]
API_CALL = re.compile(r"""(?:["'}])(?:/api/(?:prompt-repo|skills|providers|mcp|governance|plugins|config)\b)""")
SKIP_PARTS = {"tests", "test", ".venv", "node_modules", "__pycache__", "site-packages"}
KNOWN = {"register_bifrost_prompts.py", "register_bifrost_loops.py", "sync_prompts.py", "prompts.py",
         "register_bifrost_providers.py", "register_bifrost_mcp_clients.py", "register_bifrost_client_config.py",
         "register_bifrost_vk_mcp.py"}


def callers() -> list[Path]:
    found = []
    for root in ROOTS:
        for path in root.rglob("*.py"):
            if SKIP_PARTS & set(path.parts) or path.name.startswith("test_"):
                continue
            if API_CALL.search(path.read_text(errors="ignore")):
                found.append(path)
    return sorted(found)


def test_the_caller_list_is_found_and_includes_the_known_callers():
    names = {p.name for p in callers()}
    assert names, "no Bifrost /api caller found — the guard would check nothing"
    assert KNOWN <= names, f"known callers missing from the scan: {KNOWN - names}"


def test_every_bifrost_api_caller_sends_the_setup_token():
    missing = [str(p.relative_to(REPO)) for p in callers()
               if "BIFROST_SETUP_TOKEN" not in (t := p.read_text()) or "X-Bifrost-Setup-Token" not in t]
    assert not missing, "these call Bifrost's /api without the setup token (401 on v2.2.6+):\n  " + "\n  ".join(missing)
