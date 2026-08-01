"""Fail-safe role-prompt loader — live from the Bifrost Prompt Repo, else the baked fallback.

Each agent's role prompt is registered in Bifrost as `role-<key>` (system message). `load_role(spec)` fetches it,
TTL-caches it so a Bifrost edit takes effect within PROMPT_TTL without a redeploy, and falls back to `roster.fallback_prompt`
if Bifrost is unreachable or the prompt is unregistered. A registry outage never takes an agent offline (same ethos as
the operator's prompts.py against MLflow)."""
import time

import httpx

from config import BIFROST_API_URL, BIFROST_VK, HTTPX_VERIFY, PROMPT_TTL
from roster import AgentSpec, fallback_prompt

_cache: dict[str, tuple[str, float]] = {}   # key -> (system_text, fetched_at_monotonic)


def _fetch(key: str) -> str | None:
    """Return the first (system) message body of Bifrost prompt `role-<key>`, or None on any failure."""
    try:
        headers = {"x-bf-vk": BIFROST_VK} if BIFROST_VK else {}
        r = httpx.get(f"{BIFROST_API_URL}/api/prompt-repo/prompts",
                      params={"name": f"role-{key}", "limit": 1}, headers=headers, timeout=8, verify=HTTPX_VERIFY)
        r.raise_for_status()
        items = (r.json() or {}).get("prompts") or r.json() or []
        if not items:
            return None
        msgs = (items[0].get("latest_version") or items[0]).get("messages") or []
        for m in msgs:
            if m.get("role") == "system" and m.get("content"):
                return m["content"]
    except Exception:
        return None
    return None


def load_role(spec: AgentSpec) -> str:
    now = time.monotonic()
    cached = _cache.get(spec.key)
    if cached and now - cached[1] < PROMPT_TTL:
        return cached[0]
    text = _fetch(spec.key)
    if text:
        _cache[spec.key] = (text, now)
        return text
    return cached[0] if cached else fallback_prompt(spec)
