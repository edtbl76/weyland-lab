"""Brain factory — a ChatOpenAI bound to a LiteLLM `wl-*` lane.

Agents never name a provider or model; they name a use-case lane (`wl-coding`, `wl-reason`, …) and LiteLLM resolves it
to the cheapest capable provider with server-side failover. One cached client per lane."""
from functools import lru_cache

from langchain_openai import ChatOpenAI

from config import LITELLM_API_KEY, LITELLM_BASE_URL, LLM_TIMEOUT


@lru_cache(maxsize=None)
def brain(lane: str) -> ChatOpenAI:
    return ChatOpenAI(base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY, model=lane,
                      timeout=LLM_TIMEOUT, temperature=0)
