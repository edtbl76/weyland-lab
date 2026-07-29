import json
import os
import threading
import time
from collections import defaultdict, deque

from ..verdict import Verdict, Decision, Hook


class AuditValidator:
    """Act-hook audit. Always PASSes (never blocks) — it exists only to record that an action fired, with what
    params. The ENFORCING decision is `policy.gate` below."""

    name = "policy.audit"
    hooks = (Hook.ACT,)

    def check(self, payload: dict, hook: Hook) -> Verdict:
        tool = payload.get("tool", "?")
        params = payload.get("params") or {}
        reason = f"{tool} {params}" if params else tool
        return Verdict(self.name, Decision.PASS, None, reason, 0)


# --- Act policy (B17+B19 Phase 2) --------------------------------------------------------------
# Which actor may call which act tools, + a per-actor rate cap. The `actor` is the identity the MCP gateway injects
# (X-Forwarded-Consumer → the Keycloak client_id); before the gateway it is None. Env-overridable as JSON via
# GUARD_ACT_POLICY. "*" in tools = any act tool.
_DEFAULT_POLICY = {
    "weyland-operator": {"tools": ["*"], "rate_per_min": 30},
    # add one entry per agent as it comes online through the gateway (per-agent Keycloak clients → per-agent actors).
}


def _load_policy() -> dict:
    raw = os.environ.get("GUARD_ACT_POLICY")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return _DEFAULT_POLICY


class PolicyGateValidator:
    """Enforcing act policy gate. Now that the MCP gateway injects a verified `actor`, the ACT hook can allowlist which
    actor may call which act tool, rate-limit per actor, and BLOCK the rest — including acts with NO actor (a caller
    that bypassed the gateway). Ships SHADOW (records the would-block without enforcing) until every act caller is wired
    through the gateway; promote to BLOCK via `GUARDRAIL_MODE__policy__gate=block` or the /admin/mode toggle.

    Rate-limit is in-memory (single-replica guard) under a lock (shadow validators run in a threadpool)."""

    name = "policy.gate"
    hooks = (Hook.ACT,)

    def __init__(self, policy: dict | None = None):
        self._policy = policy if policy is not None else _load_policy()
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _rate_ok(self, actor: str, per_min: int) -> bool:
        with self._lock:
            now = time.monotonic()
            win = self._hits[actor]
            while win and now - win[0] > 60:
                win.popleft()
            if len(win) >= per_min:
                return False
            win.append(now)
            return True

    def check(self, payload: dict, hook: Hook) -> Verdict:
        tool = payload.get("tool", "?")
        actor = payload.get("actor")

        # 1. no identity → block. An act without an authenticated actor bypassed the gateway.
        if not actor:
            return Verdict(self.name, Decision.BLOCK, None,
                           "no actor — acts require an authenticated identity (via the MCP gateway)", 0)
        # 2. unknown actor → block.
        pol = self._policy.get(actor)
        if pol is None:
            return Verdict(self.name, Decision.BLOCK, None, f"actor '{actor}' not in the act allowlist", 0)
        # 3. tool not permitted for this actor → block.
        allowed = pol.get("tools", [])
        if "*" not in allowed and tool not in allowed:
            return Verdict(self.name, Decision.BLOCK, None, f"'{actor}' may not call '{tool}'", 0)
        # 4. per-actor rate limit → block.
        if not self._rate_ok(actor, int(pol.get("rate_per_min", 60))):
            return Verdict(self.name, Decision.BLOCK, None, f"rate limit exceeded for '{actor}'", 0)
        # 5. allow.
        return Verdict(self.name, Decision.PASS, None, f"allow {actor} -> {tool}", 0)
