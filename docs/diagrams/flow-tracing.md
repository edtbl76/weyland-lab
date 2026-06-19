# Flow: Distributed Tracing Pipeline (B8)

Why a trace shows up in Jaeger/Kiali — and why it's easy to half-wire. **Sampling alone emits nothing**:
it needs the meshConfig `extensionProvider` (zipkin) + a `Telemetry` resource selecting that provider +
a **sidecar restart** to pick up the bootstrap. Trace context (B3 headers) must be propagated by the app
across hops or each call starts a new trace.

```mermaid
sequenceDiagram
    participant App as Meshed workload
    participant Env as Envoy sidecar
    participant Tel as Telemetry mesh-default (100% sampling)
    participant Jc as Collector (zipkin.istio-system :9411, Jaeger addon)
    participant Jq as Jaeger query (:16685 + UI)
    participant K as Kiali
    App->>Env: request (B3 trace headers propagated app-side)
    Env->>Tel: span generated per Telemetry config
    Env->>Jc: report span (zipkin via extensionProvider)
    K->>Jq: query traces (gRPC :16685)
    Jq->>Jc: read stored spans
    Jq-->>K: traces
    Note over K,Jq: Kiali "View in Tracing" + workload Traces tab deep-link to jaeger.weyland.lab
```
