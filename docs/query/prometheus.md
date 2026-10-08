# Prometheus — query cookbook (PromQL)

Prometheus holds the lab's metrics. These are the PromQL queries worth keeping, grouped by the system they answer
for. Each section names the runbook that explains the system.

**Access:**
- **Grafana:** `https://grafana.weyland.lab`, then **Explore**. Pick the **Prometheus** data source, switch the
  query editor from **Builder** to **Code**, paste a query and click **Run query**. Set the time range top right to
  cover the query's window: `[24h]` needs at least **Last 24 hours**.
- **Agents:** the `grafana_query_prometheus` tool through the MCP fleet (data source uid `prometheus`).
- **In-cluster:** `prometheus-operated.monitoring.svc.cluster.local:9090`.

`increase(x[24h])` is how much a counter grew over the window, so it reads as "how many in the last 24 hours". A
counter series that has never been incremented does not exist, so **No data** is not the same as zero.

## Operator: decision-model shadow (B174)

After each incident sweep the operator asks a decision model (Jev by default, Clef-flash on demand) which tool it
should have opened with, and counts agreement with the tool qwen actually called first. Runbook:
[../runbooks/decision-models.md](../runbooks/decision-models.md).

**The evidence:** each shadow pick by backend, outcome and confidence:
```
sum by (backend, outcome, confident) (increase(operator_decide_shadow_total[24h]))
```
- `outcome`: `agree` or `disagree` with qwen's first tool; `no_baseline` means qwen called no tool; `error` means
  the call failed (key, credit or network; see the runbook's troubleshooting table).
- `confident="true"` means the model's confidence was 0.5 or higher. Read those rows on their own: the question is
  whether confident picks are right often enough to route on.
- **No data** means no sweep has handled a new alert in the window. That's normal: the shadow only runs after a
  sweep.
- **A row showing 0 can still hide a call.** `increase()` measures growth between samples, so a label combination's
  FIRST increment, the moment its series is born at 1, is invisible to it. Seen live on 2026-10-07: the first
  shadow call (`KubePodOOMKilled`, Jev `disagree`) read 0 here. While samples are few, read the running total
  instead.

**Running total since the operator pod started** (resets when the pod restarts):
```
sum by (backend, outcome, confident) (operator_decide_shadow_total)
```

**Agreement rate** as one number, 0 to 1:
```
sum(increase(operator_decide_shadow_total{outcome="agree"}[7d])) / sum(increase(operator_decide_shadow_total{outcome=~"agree|disagree"}[7d]))
```

**Agreement rate of confident picks only:**
```
sum(increase(operator_decide_shadow_total{outcome="agree",confident="true"}[7d])) / sum(increase(operator_decide_shadow_total{outcome=~"agree|disagree",confident="true"}[7d]))
```

**Jev spend in dollars** ($0.042 per million input tokens; paid from the prepaid TypeSafe credit):
```
sum(increase(operator_decide_input_tokens_total{backend="jev"}[30d])) * 0.042 / 1e6
```

**Median call latency in seconds**, per backend:
```
histogram_quantile(0.5, sum by (backend, le) (rate(operator_decide_seconds_bucket[24h])))
```

Alerts on these metrics: `OperatorDecideShadowFailing` and `OperatorDecideSpendObserved` (Grafana **Alerting**,
then **Alert rules**, under **Data source-managed**).

## Operator: brain and incident sweep (B66, B45)

Runbook: [../runbooks/operator.md](../runbooks/operator.md).

**Which brain served each request, and why.** Expect almost all `brain="local", reason="primary"`; `brain="haiku"`
is the paid failover:
```
sum by (brain, reason) (increase(operator_brain_selected_total[24h]))
```

**Sweep outcomes.** `deferred` means the local model was busy (an eval) and the sweep will retry:
```
sum by (outcome) (increase(operator_incident_sweeps_total[24h]))
```
