# Perf baseline — tool-server · AI gateway · Trino (B104)

The lab had **no throughput/latency baseline** for its request-serving services — B104's one genuinely
unbuilt gap. This is that baseline: an on-demand, bounded HTTP load harness on **k6** (Grafana's, $0 OSS,
single `grafana/k6` image, JS scripts, LGTM-native), recording to a committed baseline so later runs have
something to compare against.

## What it measures — and deliberately does NOT

Each service is driven on its **light serving-plane** endpoints, to measure the service's own throughput +
latency + concurrency handling — **not** upstream LLM inference (cost/GPU/slow) or heavy Trino
aggregations (its 4–6Gi heap has an OOM history). So:

| target | endpoint(s) | why light |
|---|---|---|
| tool-server (`192.168.1.243:30080`) | `/health`, `/ready` | the FastMCP serving plane, no tool fan-out |
| LiteLLM gateway (`192.168.1.243:30400`) | `/health/readiness` | the gateway's own routing/serving, **no completion** |
| Trino (`trino.data-mesh.svc:8080`) | `SELECT 1` | coordinator submit+poll, **no aggregation** |

## Current baseline (2026-09-10, VUs as noted)

| target | throughput | p50 | p95 | p99 | err | VUs |
|---|--:|--:|--:|--:|--:|--:|
| tool-server | 465 rps | 17.5 ms | 45.0 ms | 58.5 ms | 0.00% | 10 |
| LiteLLM gateway | 2,299 rps | 4.0 ms | 6.0 ms | 7.0 ms | 0.00% | 10 |
| Trino (`SELECT 1`) | 180 q/s | 15.0 ms | 27.4 ms | 37.8 ms | 0.00% | 3 |

Full run history (timestamped, appended per run): `tests/perf/baseline.tsv`. **Cold-start note:** the very
first Trino run showed ~8% errors that did not reproduce on a warm coordinator — treat a first-contact
blip as warm-up, not a steady-state defect; the steady-state is 0%.

## How to run (on-demand — NEVER scheduled)

```
# LAN targets (tool-server + gateway) — k6 via docker, from mother/rogueone:
bash scripts/perf-baseline.sh all          # or: toolserver | gateway

# Trino — in-cluster (ClusterIP only), ephemeral k6 Job in data-mesh, auto-cleaned:
bash scripts/perf/trino-baseline.sh
```
Knobs: `PERF_VUS` (default 10 LAN / 3 Trino) · `PERF_DURATION` (30s / 20s). k6 script: `scripts/perf/baseline.js`
(HTTP GET) and `scripts/perf/trino.js` (Trino submit-then-poll; one iteration = one full query).

## Node safety (the binding constraint)

`mother` is **swapless with ~4.6Gi peak headroom** ([[mother-ram-ceiling-hydrate-reliability]], B134/B99),
so a load test is itself a risk. The harness is **bounded by design** — low VUs + light endpoints keep it
negligible (0% errors at the levels above, node untroubled). Raise `PERF_VUS` only after watching the node
stay comfortable; the Trino Job runs **sidecar-off** (Trino has no Istio sidecar) so it reaches `trino:8080`
over plain HTTP.

## Live Grafana dashboard (optional)

Each run can also stream metrics to Prometheus via k6 remote-write (the receiver is already enabled on
kube-prometheus-stack), feeding the **"k6 Perf"** dashboard (`k8s/monitoring/k6-perf-dashboard.yaml`,
uid `k6-perf`). The dashboard exprs + units were captured from a real k6 RW run (durations are the
`k6_http_req_duration_p95/p99/avg` gauges in **seconds**; errors are `k6_http_req_failed_rate`); series
are labelled `target=<name>`.

```
# In-cluster Trino run — reaches the RW receiver directly:
PERF_GRAFANA=1 bash scripts/perf/trino-baseline.sh

# LAN runs — the RW receiver is a ClusterIP, so give k6 a LAN-reachable RW URL (expose it, or run k6
# in-cluster); otherwise the TSV is still written, just no live feed:
K6_PROMETHEUS_RW_SERVER_URL=http://<reachable>/api/v1/write bash scripts/perf-baseline.sh all
```

Because runs are on-demand + bounded (never scheduled), the dashboard shows the **most recent run within
Prometheus retention** and is empty between runs — expected. The committed TSV remains the durable record.

## Regression ratchet

`scripts/perf-ratchet.sh` compares each target's latest run against its **floor** (best p95 among prior
runs) and flags a regression when p95 drifts above `floor*(1+tol)` (default 25%) or the latest error rate
exceeds the ceiling (default 1%). **Advisory by default** (exit 0) — perf here is on-demand with little
variance data yet; arm it with `PERF_RATCHET_ENFORCE=1` to gate. **Fail-closed:** a missing/malformed
baseline is a loud error, never a silent "no regression". Guarded by `scripts/tests/perf-ratchet.bats`.

```
bash scripts/perf-ratchet.sh                    # advisory table
PERF_RATCHET_ENFORCE=1 bash scripts/perf-ratchet.sh   # gate (non-zero on regression)
```

## Scope (B104)

**k6 is the lab's adopted load-testing tool** ($0, OSS, self-hosted) — the survey's load/perf category is
answered. Baseline (TSV) + live dashboard + regression ratchet are all in place; the broader survey
refresh lives in [concepts/ai-dev-tooling-survey.md](../concepts/ai-dev-tooling-survey.md).
