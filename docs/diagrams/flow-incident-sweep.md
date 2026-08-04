# Flow: Operator incident sweep (`weyland-operator`, B45)

The operator's **enrich-only incident sweep** — a background loop that runs strictly **off the critical alert path**.
It **reads** the currently-firing alerts from Prometheus (`ALERTS{alertstate="firing"}` — which already unifies every
firing `PrometheusRule`, including the blackbox synthetic `WeylandEndpointDown` and the guardrail/service down-alerts),
dedups against Postgres, and for each **new** incident invokes the operator agent to **enrich** it (correlate recent
logs + pod status via the MCP fleet), then posts a proactive Telegram digest. Any action the agent proposes is
**dropped** — acts stay behind the Telegram confirm flow. **Hard constraint:** the paging path stays
direct Kuma/Alertmanager→Telegram; if this loop dies, paging is unaffected — that is the whole point. See
[demos/incident-sweep.md](../demos/incident-sweep.md), [runbooks/operator.md](../runbooks/operator.md),
[flow-operator-brain.md](flow-operator-brain.md), [flow-alerting.md](flow-alerting.md).

```mermaid
sequenceDiagram
    participant K as Alertmanager / Kuma
    participant TG as Telegram (you)
    participant W as sweep_loop (every 180s)
    participant P as Prometheus (prometheus-operated)
    participant DB as Postgres (operator_incidents)
    participant A as operator agent (agent.run)
    participant F as MCP fleet (loki · k8s)
    Note over K,TG: PAGING PATH — independent, always up
    K-->>TG: "X is down" (direct, never via the operator)
    Note over W,F: ENRICHMENT PATH — off the critical path, additive
    loop every INCIDENT_SWEEP_INTERVAL (180s)
        W->>P: GET /api/v1/query ALERTS{alertstate="firing"}
        P-->>W: firing alerts (labels)
        Note over W: _is_incident() — drop severity="none" + INCIDENT_SKIP_ALERTS<br/>(Watchdog, InfoInhibitor, LiteLLMEgressEnabled)
        W->>DB: incidents_recorded() → already-notified fingerprints
        loop each NEW incident (cap INCIDENT_MAX_ENRICH=5/sweep)
            W->>A: run(investigation_prompt) — "investigate, do NOT act"
            A->>F: correlate recent logs + pod/deploy status
            F-->>A: logs + pod state
            A-->>W: concise incident summary (proposal DROPPED — enrich only)
            W->>TG: 🚨 <alert> — <who>\n\n<summary>
            W->>DB: incident_record(fingerprint) — notify once per firing episode
        end
        W->>DB: incidents_clear_resolved(firing) — a re-fire notifies again
    end
    Note over W: operator_incident_sweeps_total{outcome} · operator_incidents_notified_total
```
