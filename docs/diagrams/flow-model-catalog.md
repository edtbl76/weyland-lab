# Flow: model_catalog Refresh (B26)

Dagster keeps a Postgres registry of reachable models fresh, so `list_models` reflects what's routable —
without a live fetch on every call. Scheduled (6h, cron `0 */6`) and idempotent. It fetches **all** models
from three sources and records a per-row `free` boolean (no free-filtering); pruning is replace-by-source
(`DELETE WHERE source=… ` then re-INSERT).

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
```
