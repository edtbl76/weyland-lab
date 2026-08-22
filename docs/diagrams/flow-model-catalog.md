# Flow: model_catalog Refresh (B26)

Dagster keeps a Postgres registry of reachable models fresh, so `list_models` reflects what exists —
without a live fetch on every call. Scheduled (6h, cron `0 */6`) and idempotent. It fetches **all** models
from three inventory sources (OpenRouter / Gemini / local Ollama) and records a per-row `free` boolean (no
free-filtering); pruning is replace-by-source (`DELETE WHERE source=… ` then re-INSERT). This is an
**inventory table**, distinct from what's actually routed: production traffic goes through **LiteLLM's `wl-*`
aliases**, whose hosted rungs egress via **Bifrost** (Anthropic / Groq / opencode-zen / Gemini / xAI) with
Ollama local direct. OpenRouter is now **402-unfunded** (kept as a catalog source, no longer a funded route);
Ollama local is still valid $0. See [llm-routing.md](../llm-routing.md).

```mermaid
sequenceDiagram
    participant Cron as Dagster schedule (6h)
    participant Job as weyland_catalog_job
    participant OR as OpenRouter /models
    participant GM as Gemini model list
    participant OL as Ollama /api/tags
    participant PG as Postgres model_catalog
    participant TS as tool-server /models
    Cron->>Job: trigger weyland_catalog_job
    Job->>OR: fetch all models (compute free flag)
    Job->>GM: fetch all models
    Job->>OL: fetch local models (free=true)
    Job->>PG: replace-by-source (DELETE source + INSERT) + upsert model_catalog
    TS->>PG: read model_catalog
    TS-->>TS: list_models (MCP read tool on /mcp)
    Note over OR,OL: inventory only — actual routing is LiteLLM wl-* → Bifrost (anthropic/groq/opencode-zen/gemini/xai) — OpenRouter now 402-unfunded, Ollama local still $0
```
