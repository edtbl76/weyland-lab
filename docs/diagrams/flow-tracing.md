# Flow: Distributed Tracing Pipeline (B8; → Tempo since B48)

Why a trace shows up in Grafana/Kiali — and why it's easy to half-wire. **Sampling alone emits nothing**:
it needs the meshConfig `extensionProvider` (zipkin) + a `Telemetry` resource selecting that provider +
a **sidecar restart** to pick up the bootstrap. Trace context (B3 headers) must be propagated by the app
across hops or each call starts a new trace. **Jaeger was retired in B48 (2026-06-21)** — spans now land in
**Tempo** (monolithic → MinIO); Grafana (Traces Drilldown) and Kiali both read from Tempo. `jaeger.weyland.lab`
is gone.

```mermaid
sequenceDiagram
    participant App as Meshed workload
    participant Env as Envoy sidecar
    participant Tel as Telemetry mesh-default (100% sampling)
    participant Tc as Tempo distributor (zipkin :9411)
    participant S3 as MinIO (tempo bucket)
    participant Tq as Tempo query (:3200)
    participant G as Grafana (Traces Drilldown)
    participant K as Kiali
    App->>Env: request (B3 trace headers propagated app-side)
    Env->>Tel: span generated per Telemetry config
    Env->>Tc: report span (zipkin via extensionProvider)
    Tc->>S3: store spans (object-storage backend)
    G->>Tq: query traces (Explore / Drilldown)
    K->>Tq: query traces (Tempo datasource)
    Tq->>S3: read stored spans
    Tq-->>G: traces
    Tq-->>K: traces
    Note over K,G: Kiali "View in Tracing" + Grafana Traces Drilldown (jaeger.weyland.lab retired, B48)
```
