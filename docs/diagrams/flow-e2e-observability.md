# Flow (E2E) — Observability: app emits → Prometheus / Loki / Tempo → Grafana → Alertmanager → Telegram

Cross-system thread of [flow-tracing](flow-tracing.md) and [flow-alerting](flow-alerting.md) into one picture: a
meshed workload emits all three signals (metrics, logs, traces), each lands in its store, Grafana is the single
read pane over all three, and a breached rule pages the operator on Telegram. **Tempo, not Jaeger** (Jaeger
retired B48). Demo: [../demos/observability-e2e.md](../demos/observability-e2e.md).

```mermaid
sequenceDiagram
    participant App as Meshed workload<br/>(weyland-tool-server)
    participant Env as Envoy sidecar
    participant Pr as Prometheus<br/>(metrics)
    participant Lo as Loki<br/>(logs)
    participant Te as Tempo<br/>(traces → MinIO)
    participant Gr as Grafana<br/>(grafana.weyland.lab)
    participant AM as Alertmanager
    participant Tg as Telegram<br/>(Weyland Alerts bot)

    App->>Env: request (B3 trace headers propagated app-side)
    Env->>Te: report span (zipkin via extensionProvider, 100% sampling)
    Env-->>Pr: Envoy + app metrics (scrape / PodMonitor)
    App-->>Lo: stdout logs (promtail/agent → Loki)
    Te->>Te: store spans (object-storage → MinIO)
    Gr->>Pr: query metrics (dashboards)
    Gr->>Lo: query logs (LogQL, Explore)
    Gr->>Te: query traces (Traces Drilldown)
    Pr->>Pr: evaluate alert rules
    Pr->>AM: fire alert (threshold breached)
    Lo->>AM: fire log alert (Loki ruler, same pipeline)
    AM->>AM: group + dedupe + route
    AM->>Tg: notification (+ resolve when clear)
```

**Seams made explicit:** tracing owns span → Tempo → Grafana/Kiali ([tracing](../demos/tracing.md)); alerting owns
rule → Alertmanager → Telegram ([alerting](../demos/alerting.md)). Grafana is the join point across all three
signals; metric alerts (Prometheus) and log alerts (Loki ruler) ride the **same** Alertmanager → Telegram path.
