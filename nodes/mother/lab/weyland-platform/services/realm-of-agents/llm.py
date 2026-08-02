"""Brain factory — a ChatOpenAI bound to a LiteLLM `wl-*` lane.

Agents never name a provider or model; they name a use-case lane (`wl-coding`, `wl-reason`, …) and LiteLLM resolves it
to the cheapest capable provider with server-side failover. One cached client per lane."""
from functools import lru_cache

from langchain_openai import ChatOpenAI

from config import LITELLM_API_KEY, LITELLM_BASE_URL, LLM_TIMEOUT, REALM_MODEL


def effective_model(lane: str) -> str:
    """The model actually used for `lane` after the REALM_MODEL override — what to show in logs/traces (not the
    agent's declared lane, which is misleading while the override is on)."""
    return REALM_MODEL or lane


@lru_cache(maxsize=None)
def brain(lane: str) -> ChatOpenAI:
    # REALM_MODEL (default the Haiku-backed wl-agentic lane) overrides the per-agent lane so the whole Realm runs on
    # one fast, reliable hosted brain — no rogueone cold-start hangs. Falls back to the per-agent lane if cleared.
    model = REALM_MODEL or lane
    return ChatOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY, model=model,
                      timeout=LLM_TIMEOUT, temperature=0)
