# Flow: Health / Status Aggregation (U12)

`/ready` and `/status` differ **deliberately**: readiness depends only on the embed model + pgvector, so a
non-default backend being down does NOT pull the server from the k8s rotation; `/status` reports the full
picture (overall `ok`/`degraded` = all backends ok **and** the LLM ok, plus per-backend + LLM detail).
`/health` stays a trivial liveness ping.

```mermaid
sequenceDiagram
    participant Pr as Probe / operator
    participant TS as tool-server
    participant Mdl as bge embed model (in-process flag)
    participant PgV as pgvector
    participant Oth as qdrant / weaviate / neo4j
    participant OLL as Ollama (LLM)
    Pr->>TS: GET /ready
    TS->>Mdl: model loaded? (embed_model is not None)
    TS->>PgV: reachable?
    TS-->>Pr: 200 ready (ignores Oth + LLM by design)
    Pr->>TS: GET /status
    TS->>Mdl: ok?
    TS->>PgV: ok?
    TS->>Oth: ok? (each backend)
    TS->>OLL: ok?
    TS-->>Pr: {overall: ok | degraded, per-backend + llm health}
    Note over TS: overall = all backends ok AND llm ok
```
