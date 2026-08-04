# Flow: Operator brain selection — local-primary with Haiku failover (`weyland-operator`, B45 follow-up)

Every operator turn (a Telegram message **or** an incident-sweep enrichment) picks its brain at request time. The
**primary** is a local `qwen2.5:7b` on rogueone's GPU — **$0**, non-thinking, and it tool-calls cleanly on a **curated
FLAT toolset** (READ_TOOLS + ~14 ops tools, *not* the full ~91 and *not* the two-stage routers, both of which broke
small-model tool selection). **Haiku** (via LiteLLM, the full flat 91-tool fleet) is a **health failover only**: a
request routes to it when the local engine fails a fast cached health pre-check, or errors/stalls past a short 60s
per-call timeout. So a rogueone/Ollama outage — or the card saturating (e.g. on-demand llama-guard-8b resident) —
**degrades to paid cloud instead of going dark**, and steady-state Haiku spend ≈ **$0**. See
[flow-operator.md](flow-operator.md), [flow-incident-sweep.md](flow-incident-sweep.md),
[runbooks/operator.md](../runbooks/operator.md).

```mermaid
sequenceDiagram
    participant C as caller (Telegram turn / sweep enrichment)
    participant R as agent.run
    participant H as health pre-check (Ollama /api/tags, ~3s, cached 30s)
    participant Lo as local qwen2.5:7b (rogueone Ollama, curated FLAT ~14 tools)
    participant Ha as Haiku (LiteLLM → full flat 91-tool fleet)
    C->>R: run(message)
    R->>H: local healthy? (cached)
    alt healthy (or fallback disabled)
        R->>Lo: ainvoke (per-call timeout 60s)
        alt local answers in time
            Lo-->>R: reply / proposal
            Note over R: operator_brain_selected_total{brain="local",reason="primary"}
            R-->>C: reply (~15s, $0)
        else local errors OR stalls > 60s
            Note over R: mark local down (next request skips it fast)
            R->>Ha: ainvoke (same messages, fresh attempt)
            Ha-->>R: reply / proposal
            Note over R: operator_brain_selected_total{brain="haiku",reason="local_error"}
            R-->>C: reply (paid)
        end
    else pre-check miss (rogueone/Ollama down or slow)
        R->>Ha: ainvoke (skip local — no 60s wait)
        Ha-->>R: reply / proposal
        Note over R: operator_brain_selected_total{brain="haiku",reason="local_down"}
        R-->>C: reply (paid)
    end
    Note over R: Haiku selections are the failover signal — watch operator_brain_selected_total; sustained > $5/24h → LiteLLMSpendObserved
```
