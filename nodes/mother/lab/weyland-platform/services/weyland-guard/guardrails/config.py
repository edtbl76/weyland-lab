import os
from .verdict import Hook, Mode

# (validator_name, mode) per hook. Everything ships SHADOW. Override a mode via env
# GUARDRAIL_MODE__<validator>=block|flag|off  (dots in the name -> double underscore),
# or LIVE (no restart) via POST /admin/mode — see the override machinery below.
_DEFAULT = {
    Hook.INPUT: [
        ("llm_guard.injection", Mode.SHADOW),
    ],
    Hook.OUTPUT: [
        ("llm_guard.pii", Mode.SHADOW),       # B34: baked + entity-calibrated (IP/UUID dropped); SHADOW until the
                                              #   false-positive rate is measured on real traffic (then promote).
        ("llm_guard.toxicity", Mode.SHADOW),
        ("grounding.nli", Mode.SHADOW),
    ],
    Hook.ACT: [
        ("policy.audit", Mode.SHADOW),   # audit-only record that an act fired.
        ("policy.gate", Mode.SHADOW),    # B17+B19 Phase 2: ENFORCING allowlist / rate-limit / block, keyed on the
                                         #   gateway-injected actor. SHADOW until every act caller routes through the
                                         #   gateway (else NULL-actor acts would block), then promote to `block`.
    ],
}

# --- Runtime mode overrides (the demo toggle) --------------------------------------------------
# Flip validator modes LIVE via POST /admin/mode — takes precedence over env + defaults. IN-PROCESS
# only (never persisted): a pod restart drops back to the committed/env modes, so a demo left "on" by
# accident self-heals, and there's no manifest drift for Argo to fight. This is the toggle for
# temporarily un-shadowing the guards for a demo, then reverting.
_OVERRIDES: dict[str, Mode] = {}


def all_validators() -> list[str]:
    return sorted({name for chain in _DEFAULT.values() for name, _ in chain})


def set_override(name: str, mode: Mode | None) -> None:
    if mode is None:
        _OVERRIDES.pop(name, None)
    else:
        _OVERRIDES[name] = mode


def clear_overrides() -> None:
    _OVERRIDES.clear()


def current_overrides() -> dict[str, str]:
    return {k: v.value for k, v in _OVERRIDES.items()}


def _mode_for(name: str, default: Mode) -> Mode:
    if name in _OVERRIDES:                       # live demo override wins over env + default
        return _OVERRIDES[name]
    raw = os.environ.get("GUARDRAIL_MODE__" + name.replace(".", "__"))
    return Mode(raw) if raw else default


def hook_chain(hook: Hook) -> list[tuple[str, Mode]]:
    return [(name, _mode_for(name, default)) for name, default in _DEFAULT.get(hook, [])]
