# Flow: Guardrail Validation (B14 + B70 Part 2 + B115 Classify — shared `weyland-guard` service)

Every `/context/*` call runs validator chains at the **INPUT** and **OUTPUT** hooks. Since B70 Part 2 the validators
live in a **standalone `weyland-guard` service** — the tool-server POSTs each hook to it over HTTP instead of running
models in-process. All validators ship **SHADOW** (fire-and-forget telemetry, never block); a mode flips to
`block`/`flag` via `GUARDRAIL_MODE__<validator>` env on `weyland-guard`. Active chains: INPUT = `prompt_guard.injection` +
`llama_guard.safety`; OUTPUT = `pii.presidio` + `grounding.nli` + `llama_guard.safety` (safety = toxicity since B117). The
**Classify** validator `llama_guard.safety` (B115) POSTs to the `llama-guard` svc — a Llama Guard content-safety
classifier (tier-1 1B on CPU/mother; on-demand 8B on the rogueone GPU) — and is itself fail-open. Enforcing ACT policy = B35.
The tool-server calls **fail-open**: a guard outage degrades to "not guarded", never "no answer". See
[runbooks/guardrails.md](../runbooks/guardrails.md).

```mermaid
sequenceDiagram
    participant C as Client
    participant TS as tool-server /context/ask
    participant G as weyland-guard service
    participant V as Validators (baked models)
    participant LG as llama-guard (Classify svc)
    participant PM as Prometheus /metrics
    participant PG as Postgres guardrail_verdicts
    C->>TS: POST /context/ask {query} (actor = X-Forwarded-Consumer)
    TS->>G: POST /guard/input {request_id, query, actor}
    Note over TS,G: fail-open — any error/timeout => allow
    G->>V: prompt_guard.injection + llama_guard.safety (shadow, fire-and-forget)
    V->>LG: llama_guard.safety: classify prompt (temp 0)
    LG-->>V: safe | unsafe/S<cat>
    G-->>TS: {decision: allow} (fast — models score async)
    V-->>PM: observe(hook, mode, verdict)
    V-->>PG: record_verdict(... actor)
    Note over V,PM: actor is high-cardinality -> DB only, never a metric label
    TS->>TS: retrieve chunks + generate answer
    TS->>G: POST /guard/output {request_id, answer, sources, actor}
    G->>V: pii.presidio + grounding.nli + llama_guard.safety (safety=toxicity)
    V->>LG: llama_guard.safety: classify answer (temp 0)
    LG-->>V: safe | unsafe/S<cat>
    G-->>TS: {decision: allow|block}
    V-->>PM: verdicts
    V-->>PG: verdicts
    TS-->>C: answer (unblocked in shadow — enforcing mode would return block => 403)
```
