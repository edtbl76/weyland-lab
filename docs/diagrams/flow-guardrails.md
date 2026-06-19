# Flow: Guardrail Validation (B14, shadow-first)

Every `/context/*` call runs validator chains at the **INPUT** and **OUTPUT** hooks. All validators ship
**SHADOW** (fire-and-forget telemetry, never block); a mode flips to `block`/`flag` via
`GUARDRAIL_MODE__<validator>` env. Active chain: INPUT = `llm_guard.injection`; OUTPUT = `llm_guard.toxicity`
+ `grounding.nli` (PII validator is coded but **deferred** — model not baked). Enforcing policy gate = B35.

```mermaid
sequenceDiagram
    participant C as Client
    participant TS as tool-server /context/ask
    participant G as Guardrail pipeline (daemon loop)
    participant V as Validators
    participant PM as Prometheus /metrics
    participant PG as Postgres guardrail_verdicts
    C->>TS: POST /context/ask {query} (actor = X-Forwarded-Consumer)
    TS->>G: _guard(INPUT, {query})
    G->>V: llm_guard.injection (shadow)
    V-->>G: verdict
    G->>PM: observe(hook, mode, verdict)
    G->>PG: record_verdict(... actor)
    Note over G,PM: actor is high-cardinality -> DB only, never a metric label
    TS->>TS: retrieve chunks + generate answer
    TS->>G: _guard(OUTPUT, {answer, sources})
    G->>V: llm_guard.toxicity + grounding.nli (answer vs chunks)
    V-->>G: verdicts -> PM + PG
    TS-->>C: answer (unblocked in shadow — enforcing would wait up to GUARDRAIL_BLOCK_TIMEOUT)
```
