from ..verdict import Verdict, Decision, Hook


class AuditValidator:
    """Act-hook audit. Always PASSes (shadow, never blocks) — it exists only to record that an action
    fired, with what params. The enforcing policy gate (allowlist/rate-limit/block) lands later with B35."""

    name = "policy.audit"
    hooks = (Hook.ACT,)

    def check(self, payload: dict, hook: Hook) -> Verdict:
        tool = payload.get("tool", "?")
        params = payload.get("params") or {}
        reason = f"{tool} {params}" if params else tool
        return Verdict(self.name, Decision.PASS, None, reason, 0)
