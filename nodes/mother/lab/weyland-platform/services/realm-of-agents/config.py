"""Runtime config for the Realm of Agents (B17 A2A).

One multiplexed pod hosts all agents. Brains route through the LiteLLM `wl-*` lanes (transparent failover); tools come
from the Bifrost VK MCP surface (the same 232-tool `coding-agents` key the coding agents use). Everything is env-tunable
and fail-safe — an unreachable LiteLLM/Bifrost degrades an agent, it never crashes the pod."""
import os

VERSION = "0.1.0"

# --- Brains: LiteLLM wl-* lanes (OpenAI-compatible) ---------------------------------------------------------------
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://litellm.weyland.svc.cluster.local:4000/v1")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-litellm")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))

# --- Tools: the Bifrost VK MCP surface ---------------------------------------------------------------------------
# CoreDNS forwards *.weyland.lab to LAN DNS, so the pod can resolve the ingress host directly.
BIFROST_MCP_URL = os.getenv("BIFROST_MCP_URL", "https://bifrost.weyland.lab/mcp")
BIFROST_API_URL = os.getenv("BIFROST_API_URL", "https://bifrost.weyland.lab")
BIFROST_VK = os.getenv("BIFROST_VK", "")          # x-bf-vk header; empty → agents run tool-less (still answer)

# TLS: *.weyland.lab uses a self-signed lab CA. Mount that CA and point BIFROST_CA_BUNDLE at it so we verify against it
# rather than disabling verification (which would allow MITM). Empty → system trust store. Never verify=False.
BIFROST_CA_BUNDLE = os.getenv("BIFROST_CA_BUNDLE", "")
HTTPX_VERIFY = BIFROST_CA_BUNDLE or True

# --- Prompt Repo (fail-safe): live role prompts by name, else the baked fallback in roster.py --------------------
PROMPT_TTL = float(os.getenv("PROMPT_TTL", "300"))

# --- Server ------------------------------------------------------------------------------------------------------
PORT = int(os.getenv("PORT", "8080"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://realm.weyland.lab")   # advertised in Agent Cards
