"""Fail-safe role-prompt loader — live from the Bifrost Prompt Repo, else the baked fallback.

Each agent's role prompt is registered in Bifrost as `role-<key>` (system message). `load_role(spec)` fetches it,
TTL-caches it so a Bifrost edit takes effect within PROMPT_TTL without a redeploy, and falls back to `roster.fallback_prompt`
if Bifrost is unreachable or the prompt is unregistered. A registry outage never takes an agent offline (same ethos as
the operator's prompts.py against MLflow)."""
import os
import time

import httpx

from config import BIFROST_API_URL, BIFROST_VK, HTTPX_VERIFY, PROMPT_TTL
from roster import AgentSpec, fallback_prompt

BIFROST_HEADERS = {"X-Bifrost-Setup-Token": os.environ["BIFROST_SETUP_TOKEN"]} if os.getenv("BIFROST_SETUP_TOKEN") else {}  # B202: v2.2.6+ setup lock (auth off)

_cache: dict[str, tuple[str, float]] = {}   # key -> (system_text, fetched_at_monotonic)


def _fetch(key: str) -> str | None:
    """Return the first (system) message body of Bifrost prompt `role-<key>`, or None on any failure."""
    try:
        headers = {**BIFROST_HEADERS, **({"x-bf-vk": BIFROST_VK} if BIFROST_VK else {})}
        # Bifrost IGNORES name/limit here and returns every prompt, newest first (observed 2026-10-09) — so select by
        # exact name, never by list position (items[0] was some other prompt, so every agent fell back silently).
        r = httpx.get(f"{BIFROST_API_URL}/api/prompt-repo/prompts",
                      params={"limit": 1000}, headers=headers, timeout=8, verify=HTTPX_VERIFY)
        r.raise_for_status()
        items = (r.json() or {}).get("prompts") or []
        match = next((p for p in items if p.get("name") == f"role-{key}"), None)
        if match is None:
            return None
        for m in (match.get("latest_version") or {}).get("messages") or []:
            msg = m.get("message") or m          # each message is wrapped: {"message": {"role", "content"}, ...}
            if msg.get("role") == "system" and msg.get("content"):
                return msg["content"]
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
