# Flow: Guardrail Validation (B14 + B70 Part 2 — shared `weyland-guard` service)

Every `/context/*` call runs validator chains at the **INPUT** and **OUTPUT** hooks. Since B70 Part 2 the validators
live in a **standalone `weyland-guard` service** — the tool-server POSTs each hook to it over HTTP instead of running
models in-process. All validators ship **SHADOW** (fire-and-forget telemetry, never block); a mode flips to
`block`/`flag` via `GUARDRAIL_MODE__<validator>` env on `weyland-guard`. Active chains: INPUT = `llm_guard.injection`;
OUTPUT = `llm_guard.toxicity` + `grounding.nli` (PII coded but **deferred** — not baked). Enforcing ACT policy = B35.
The tool-server calls **fail-open**: a guard outage degrades to "not guarded", never "no answer". See
[runbooks/guardrails.md](../runbooks/guardrails.md).

```mermaid
sequenceDiagram
    participant C as Client
    participant TS as tool-server /context/ask
    participant G as weyland-guard service
    participant V as Validators (baked models)
    participant PM as Prometheus /metrics
    participant PG as Postgres guardrail_verdicts
    C->>TS: POST /context/ask {query} (actor = X-Forwarded-Consumer)
    TS->>G: POST /guard/input {request_id, query, actor}
    Note over TS,G: fail-open — any error/timeout => allow
    G->>V: llm_guard.injection (shadow, fire-and-forget)
    G-->>TS: {decision: allow} (fast — model scores async)
    V-->>PM: observe(hook, mode, verdict)
    V-->>PG: record_verdict(... actor)
    Note over V,PM: actor is high-cardinality -> DB only, never a metric label
    TS->>TS: retrieve chunks + generate answer
    TS->>G: POST /guard/output {request_id, answer, sources, actor}
    G->>V: llm_guard.toxicity + grounding.nli (answer vs sources)
    G-->>TS: {decision: allow|block}
    V-->>PM: verdicts
    V-->>PG: verdicts
    TS-->>C: answer (unblocked in shadow — enforcing mode would return block => 403)
```
