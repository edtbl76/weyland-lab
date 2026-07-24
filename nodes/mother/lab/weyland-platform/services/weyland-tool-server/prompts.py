"""Fail-safe MLflow Prompt Registry client (B100 Phase 2).

`load_prompt(name, fallback)` returns the registered `production` template for `name`, TTL-cached so a version bump
(via scripts/register_prompts.py) takes effect within PROMPT_TTL with no redeploy — without an MLflow round-trip on
every call. FAIL-SAFE: MLflow unreachable or the prompt unregistered → the last-cached value, else the baked
`fallback`. A registry outage never takes a request offline (same ethos as the guard + the tracing)."""
import os
import time

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "")
PROMPT_TTL = float(os.getenv("PROMPT_TTL", "300"))
PROMPT_ALIAS = os.getenv("PROMPT_ALIAS", "production")
_cache: dict = {}   # name -> (template, version, fetched_at_monotonic)


def load_prompt(name: str, fallback: str) -> str:
    """Return the live `production` template for `name` (TTL-cached), or the fail-safe fallback."""
    now = time.monotonic()
    cached = _cache.get(name)
    if cached and now - cached[2] < PROMPT_TTL:
        return cached[0]
    if not MLFLOW_TRACKING_URI:
        return cached[0] if cached else fallback
    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        pv = mlflow.load_prompt(f"prompts:/{name}@{PROMPT_ALIAS}")
        _cache[name] = (pv.template, str(pv.version), now)
        return pv.template
    except Exception:
        return cached[0] if cached else fallback


def loaded_version(name: str) -> str | None:
    """The version of the last successfully-fetched prompt (for trace tagging), or None if never fetched."""
    c = _cache.get(name)
    return c[1] if c else None
