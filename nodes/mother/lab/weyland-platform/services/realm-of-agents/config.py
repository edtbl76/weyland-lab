"""Runtime config for the Realm of Agents (B17 A2A).

One multiplexed pod hosts all agents. Brains route through the LiteLLM `wl-*` lanes (transparent failover); tools come
from the Bifrost VK MCP surface (the same 232-tool `coding-agents` key the coding agents use). Everything is env-tunable
and fail-safe — an unreachable LiteLLM/Bifrost degrades an agent, it never crashes the pod."""
import os

VERSION = "0.3.1"   # 0.3.0: /route/stream SSE. 0.3.1: Realm Console served at GET / + final-answer/scaffolding stream fixes
# A2A Protocol revision advertised in every Agent Card (`protocolVersion`). Matches the spec the current a2a-sdk /
# a2a-inspector expect; the JSON-RPC `message/send` binding lives in a2a.py.
A2A_PROTOCOL_VERSION = "0.3.0"

# --- Brains: LiteLLM wl-* lanes (OpenAI-compatible) ---------------------------------------------------------------
LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://litellm.weyland.svc.cluster.local:4000/v1")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-litellm")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))
# Brain override: the WHOLE Realm thinks with one reliable hosted model instead of per-agent lanes. Default = the
# wl-agentic lane (Claude Haiku primary + a free hosted fallback tail), because the local rogueone lanes
# (wl-reason/wl-rag) cold-start-hang and we want that GPU idle. Set REALM_MODEL="" to restore per-agent lanes,
# or ="claude-haiku" to pin to raw Haiku with no fallback.
REALM_MODEL = os.getenv("REALM_MODEL", "wl-agentic")

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

# --- Observability: MLflow traces (every run + its deliverable captured; fail-safe if MLflow is down) ------------
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "realm-of-agents")

# --- Server ------------------------------------------------------------------------------------------------------
PORT = int(os.getenv("PORT", "8080"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://realm.weyland.lab")   # advertised in Agent Cards
