# Observability signals — metrics · logs · traces · profiles (runbook)

The weyland observability stack in Grafana (`grafana.weyland.lab`), all in ns `monitoring`, all LAN/self-hosted ($0):

| Signal | Backend | Datasource (uid) | Source |
|---|---|---|---|
| **Metrics** | Prometheus (kube-prometheus-stack) | `prometheus` | ServiceMonitors scrape `/metrics` |
| **Logs** | Loki | `loki` | Alloy DaemonSet tails pod logs → Loki |
| **Traces** | Tempo (monolithic → MinIO) | `tempo` | Istio (zipkin) + OTLP receivers |
| **Profiles** | Pyroscope (monolithic `:4040`) | `pyroscope` | Alloy `pyroscope.scrape` pprof → Pyroscope |

Config: `k8s/monitoring/kube-prometheus-stack-values.yaml` (Prometheus + Grafana datasources), `k8s/loki/alloy-values.yaml`
(Alloy: logs **and** profiling), `k8s/tempo/tempo-values.yaml`, `k8s/pyroscope/pyroscope.yaml`.

---

## B111 — traces → Prometheus metrics (Tempo metrics-generator)

**Symptom:** Traces Drilldown "Span rate" 500s with `error finding generators: empty ring`. **Cause:** Tempo's
metrics-generator was never enabled (`overrides.defaults: {}`), so no generator joins the ring. **Fix (two ends):**
- Tempo `metricsGenerator.enabled: true` + `remoteWriteUrl` → Prometheus (default processors: service-graphs,
  span-metrics, local-blocks — `local-blocks` powers the TraceQL `rate()` "Span rate" view).
- Prometheus `enableRemoteWriteReceiver: true` — else the generator's `remote_write` is refused.

**Verify (after Argo sync):**
```
# metrics_generator now in the rendered Tempo config (not empty)
kubectl -n monitoring exec tempo-0 -- wget -qO- localhost:3200/status/config | grep -A6 metrics_generator
# span-metrics / service-graph series landed in Prometheus
kubectl -n monitoring exec deploy/monitoring-kube-prometheus-prometheus -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/label/__name__/values' | grep -o 'traces_[a-z_]*'
```
Then in Grafana: Drilldown → Traces → the "Span rate" panel populates (no `empty ring`). **Watch Tempo memory** —
`local-blocks` holds recent traces in RAM; limit raised 3Gi→4Gi (Tempo is OOM-prone, [[node-oom-forensics]]).

## B111 — profiles (Pyroscope)

Monolithic Pyroscope (`grafana/pyroscope`, `-target=all`, `:4040`, emptyDir storage for now). Alloy scrapes the Go
services' `/debug/pprof` and forwards to it (`pyroscope.scrape "go_services"` → `pyroscope.write`). Grafana datasource
`pyroscope` unlocks the **Profiles Drilldown**.

**Verify (after sync):**
```
kubectl -n monitoring get pod -l app=pyroscope           # Ready
kubectl -n monitoring exec deploy/pyroscope -- wget -qO- localhost:4040/ready   # ready
# ingestion: after Alloy rolls, Pyroscope should list scraped apps
kubectl -n monitoring exec deploy/pyroscope -- wget -qO- 'localhost:4040/pyroscope/api/apps' 2>/dev/null | head
```
Grafana → Drilldown → Profiles → pick service `tempo`/`loki` → flame graph renders.

**Open follow-up (ingestion breadth):** only Tempo + Loki are scraped today. Add more targets to
`pyroscope.scrape` in `alloy-values.yaml` once their pprof endpoint is confirmed (Bifrost/Prometheus/etc.), or
instrument app-level services with the Pyroscope SDK. Until a target is added, its profiles are absent — not an error.

## Signal wiring is a DoD gate

Per [definition-of-done.md](../definition-of-done.md) pillar 6, a new service must cover all four signals (or note N/A):
metrics (ServiceMonitor + dashboard), logs (Loki), traces (Tempo, or metrics-as-tracing for single-hop), profiles
(Pyroscope where it's a pprof/SDK target).
