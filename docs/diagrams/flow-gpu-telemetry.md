# Flow: rogueone GPU telemetry (B128)

rogueone's DCGM host engine feeds a snap `dcgm-exporter` on `:9400`; in-cluster Prometheus scrapes it as a static
off-cluster target, Grafana charts it, and two PrometheusRules turn GPU faults and thermals into pages. The target
flaps down when the laptop sleeps — that is covered by the blanket TargetDown net (no dedicated down alert), same
as the existing ray-worker target on the same box.

```mermaid
sequenceDiagram
    autonumber
    participant DCGM as DCGM host engine<br/>(rogueone)
    participant EXP as dcgm-exporter :9400<br/>(rogueone, snap)
    participant PROM as Prometheus<br/>(in-cluster, mother)
    participant GRAF as Grafana dashboard<br/>(rogueone GPU DCGM)
    participant RULE as PrometheusRule<br/>(dcgm-gpu)
    participant AM as Alertmanager to Telegram
    DCGM->>EXP: poll RTX 5000 Ada (util, VRAM, temp, power, clocks, Xid)
    PROM->>EXP: scrape static target 192.168.1.230:9400 /metrics
    EXP-->>PROM: DCGM_FI_DEV_ series, label gpu_host rogueone
    PROM->>GRAF: dashboard queries filtered by job dcgm-exporter-rogueone
    PROM->>RULE: evaluate GpuXidError and GpuHighTemp
    RULE-->>AM: fire on Xid nonzero (critical), or temp over 85C for 5m (warning)
    AM-->>DCGM: page the operator (Telegram)
    Note over PROM,EXP: laptop sleep drops the target — blanket TargetDown covers it (no dedicated down alert)
```
