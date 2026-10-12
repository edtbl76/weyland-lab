"""Brain factory — a ChatOpenAI bound to a LiteLLM `wl-*` lane.

Agents never name a provider or model; they name a use-case lane (`wl-coding`, `wl-reason`, …) and LiteLLM resolves it
to the cheapest capable provider with server-side failover. One cached client per resolved model."""
from functools import lru_cache

from langchain_openai import ChatOpenAI

from budget import is_free_only
from config import LITELLM_API_KEY, LITELLM_BASE_URL, LLM_TIMEOUT, REALM_FREE_MODEL, REALM_MODEL


def effective_model(lane: str) -> str:
    """The model actually used for `lane` after the REALM_MODEL override (or the free lane, in a free-only request) —
    what to show in logs/traces (not the agent's declared lane, which is misleading while an override is on)."""
    if is_free_only():
        return REALM_FREE_MODEL
    return REALM_MODEL or lane


def brain(lane: str) -> ChatOpenAI:
    # REALM_MODEL (default the Haiku-backed wl-agentic lane) overrides the per-agent lane so the whole Realm runs on
    # one fast, reliable hosted brain — no rogueone cold-start hangs. Falls back to the per-agent lane if cleared.
    # A free-only request gets the free lane with LiteLLM fallbacks OFF: wl-judge's chain reaches wl-default, whose
    # own chain ends at the paid wl-agentic, so "free" holds only if no fallback runs.
    return _client(effective_model(lane), is_free_only())


@lru_cache(maxsize=None)
def _client(model: str, free_only: bool) -> ChatOpenAI:
    extra = {"extra_body": {"disable_fallbacks": True}} if free_only else {}
    return ChatOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY, model=model,
                      timeout=LLM_TIMEOUT, temperature=0, **extra)
