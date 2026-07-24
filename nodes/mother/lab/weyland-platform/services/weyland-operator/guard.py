"""Fail-open client to the shared weyland-guard service (B70) — lifted verbatim from weyland-agent."""
import os

import httpx

GUARD_BASE_URL = os.getenv("GUARD_BASE_URL", "http://weyland-guard.weyland.svc.cluster.local:8080")
GUARD_TIMEOUT = float(os.getenv("GUARD_TIMEOUT", "10"))
_PATHS = {"input": "/guard/input", "output": "/guard/output", "act": "/guard/act"}


def guard(hook: str, request_id: str, payload: dict, actor: str | None = None) -> dict | None:
    """POST a hook to weyland-guard. Returns the blocking verdict dict if blocked, else None. FAIL-OPEN: any
    error/timeout/unreachable → None (allow) — a guard outage must never take a reply offline."""
    body = {"request_id": request_id, "actor": actor, **payload}
    try:
        r = httpx.post(f"{GUARD_BASE_URL}{_PATHS[hook]}", json=body, timeout=GUARD_TIMEOUT)
        data = r.json()
        return data.get("verdict") if data.get("decision") == "block" else None
    except Exception:
        return None
