import os
from .verdict import Hook, Mode

# (validator_name, mode) per hook. Everything ships SHADOW. Override a mode via env
# GUARDRAIL_MODE__<validator>=block|flag|off  (dots in the name -> double underscore).
_DEFAULT = {
    Hook.INPUT: [
        ("llm_guard.injection", Mode.SHADOW),
    ],
    Hook.OUTPUT: [
        # ("llm_guard.pii", Mode.SHADOW),   # DEFERRED (B14): validator coded but unbaked —
        #   presidio/spaCy model not in the image. Re-enable this line once the PII model is
        #   baked (see roadmap "Evaluate + bake PII guard"). Until then it would only record
        #   "validator not loaded" PASS noise, so it's kept out of the active chain.
        ("llm_guard.toxicity", Mode.SHADOW),
        ("grounding.nli", Mode.SHADOW),
    ],
    Hook.ACT: [],   # reserved for D
}


def _mode_for(name: str, default: Mode) -> Mode:
    raw = os.environ.get("GUARDRAIL_MODE__" + name.replace(".", "__"))
    return Mode(raw) if raw else default


def hook_chain(hook: Hook) -> list[tuple[str, Mode]]:
    return [(name, _mode_for(name, default)) for name, default in _DEFAULT.get(hook, [])]
