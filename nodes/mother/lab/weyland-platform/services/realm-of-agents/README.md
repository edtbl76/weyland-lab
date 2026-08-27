# realm-of-agents (B17 — Agent-to-Agent)

One multiplexed pod hosting the **Realm of Agents** — 24 small, corpus-backed agents in five groups, realm-partitioned
inside. Each agent = a role prompt (Bifrost Prompt Repo) + a skill family + a slice of the Bifrost VK MCP tools + a
LiteLLM `wl-*` brain. Design & full roster: `docs/design/a2a-agent-roster.md`; public map: `docs/concepts/realm-of-agents.md`.

## Shape

- **`roster.py`** — the single source of truth: all 24 `AgentSpec`s (realm, role, plain job, lane, tool subsystems,
  lead/members). Add an agent here and it flows to the cards, the router, and the runnable graphs.
- **`cards.py`** — A2A-shaped Agent Cards (per agent + a root card).
- **`agents.py`** — build/run one agent (ReAct: brain + tools + role prompt).
- **`realms.py`** — a lead delegates to its members (member-as-tool → real 2-hop delegation).
- **`router.py`** — Gná: classify a task → run the best-fit agent.
- **`llm.py` / `fleet.py` / `prompts.py`** — brains (LiteLLM lanes), tools (Bifrost VK, fail-safe), role prompts
  (Bifrost, fail-safe to baked fallbacks).
- **`app.py`** — the A2A HTTP surface.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/.well-known/agent-card.json` | Root card — discover the whole realm |
| GET | `/agents` | Every agent card + a realm index |
| GET | `/agents/{key}/card` (or `/.well-known/agent-card.json`) | One agent's card |
| POST | `/agents/{key}/message` | Send a task to a specific agent (`{"message": "..."}`) |
| POST | `/route` | Gná dispatch — pick the best agent and run it |
| GET | `/health` · `/ready` · `/metrics` | Ops |

## Config (env)

- `LITELLM_BASE_URL` (default in-cluster LiteLLM `:4000/v1`), `LITELLM_API_KEY` (LiteLLM master key).
- `BIFROST_VK` — the `coding-agents` virtual key; empty → agents run tool-less (still answer).
- `BIFROST_MCP_URL` / `BIFROST_API_URL` — default the `bifrost.weyland.lab` ingress; point at the in-cluster Bifrost
  Service (plain http) to skip TLS to the self-signed ingress.
- `BIFROST_CA_BUNDLE` — path to the mounted lab CA for verifying `*.weyland.lab` (never disable verification).
- `PUBLIC_BASE_URL` — advertised in Agent Cards.

## Slice 1 (first wave)

Gná dispatch · **Kvasir** (pure-corpus peer) · **Verðandi** (grafana tools; first job = the B109 dashboard audit) ·
**Odin** delegating to **Mímir** + **Brokkr** (intra-realm LangGraph). Every other agent is declared and runs
generically; leads gain delegation as their members come online.

## Build & run

```
docker build -t registry.weyland.lab/realm-of-agents:v1 .
# local smoke (tool-less, no VK): uvicorn app:app --port 8080  then  curl :8080/agents
```
