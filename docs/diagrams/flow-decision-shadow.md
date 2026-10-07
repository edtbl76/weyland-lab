# Flow: decision-model shadow on the incident sweep (`weyland-operator`, B174)

After the incident sweep's agent has enriched an alert and the digest is posted, the operator asks a **decision model**
the same question as one typed `choice`: which tool should it have opened with? It then counts whether that matches the
tool qwen actually called first. It is a **shadow**:
- nothing acts on the pick, and it never reaches the digest;
- a deferred or failed run is not shadowed, since there is no baseline and the paid call would buy nothing;
- every failure is counted as an error, never as agreement.

**Backends:** Jev (TypeSafe's hosted API, paid from the owner's prepaid credit) is the default. Clef-flash on rogueone
`:8004` is the same API, used on demand. The API key rides https only. See
[runbooks/decision-models.md](../runbooks/decision-models.md), [concepts/decision-models.md](../concepts/decision-models.md),
[flow-incident-sweep.md](flow-incident-sweep.md).

```mermaid
sequenceDiagram
    participant W as incident sweep (incidents.py)
    participant A as operator agent (agent.run)
    participant TG as Telegram digest
    participant D as decide.shadow (decide.py)
    participant J as Jev API (api.typesafe.ai, https + key)
    participant C as Clef-flash (rogueone 8004, on demand, http, no key)
    participant M as Prometheus metrics
    W->>A: run(investigation prompt, allow_fallback=false, trace)
    alt local brain busy or down
        A-->>W: LocalUnavailable, sweep defers
        Note over W,D: no shadow call, the next sweep retries the alert
    else enrichment failed
        A-->>W: error, digest says "enrichment failed"
        W->>TG: digest
        Note over W,D: no trace means no baseline, so no shadow call
    else enriched
        A-->>W: reply + trace.first_tool (the first tool qwen called)
        W->>TG: digest (unchanged by the shadow)
        alt OPERATOR_DECIDE_SHADOW = true
            W->>D: shadow(rules, same prompt, sweep_tools(), actual=first_tool)
            alt OPERATOR_DECIDE_URL = TypeSafe (default)
                D->>J: POST /v1/systemone (one choice question over the tools)
                J-->>D: choice + confidence + input_tokens
            else OPERATOR_DECIDE_URL = rogueone 8004
                D->>C: POST /v1/systemone (same body)
                C-->>D: choice + confidence
            end
            alt answer parsed
                D->>M: shadow_total{outcome=agree, disagree or no_baseline, confident} + input_tokens + seconds
            else HTTP error, bad body or network failure
                D->>M: shadow_total{outcome=error}, logged, returns None
            end
            Note over M: OperatorDecideShadowFailing = only errors for 2h<br/>OperatorDecideSpendObserved = more than 1 dollar of Jev in 24h
        end
    end
```
