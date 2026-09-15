# Demo — rogueone GPU telemetry (B128)

Turn rogueone's already-running DCGM host engine into live GPU observability: enable the snap `dcgm-exporter`,
scrape it into the in-cluster LGTM stack as a static off-cluster target, and get a Grafana dashboard plus fault
(Xid) and thermal alerts. The payoff is **early warning** — the `NVRM Xid 16` events that only showed up
post-mortem in `dmesg` during the freeze forensics (EMA-186) now surface in Grafana and page via Telegram.

Runbook: [runbooks/observability.md](../runbooks/observability.md) (dcgm-exporter section) · flow:
[flow-gpu-telemetry](../diagrams/flow-gpu-telemetry.md).

> **Status: RUN 2026-09-15.** Exporter enabled on rogueone; all `DCGM_FI_DEV_*` serving on `:9400` (incl.
> `XID_ERRORS`, in the default field set); Prometheus target `up{job="dcgm-exporter-rogueone"}=1`; metrics flowing
> (`GPU_TEMP` 56C, `XID_ERRORS` 0 / No Error, `FB_USED` ~6 GiB); dashboard ConfigMap + `dcgm-gpu` PrometheusRule
> Argo-synced (`monitoring-extras`). GPU: NVIDIA RTX 5000 Ada Laptop, driver 595.71.05.

## #1 — Enable the exporter (operator, on rogueone)

The DCGM host engine (`dcgm.nv-hostengine`) is already active; only the exporter is disabled.

```
[rogueone] sudo snap start --enable dcgm.dcgm-exporter
[rogueone] curl -s localhost:9400/metrics | grep -E 'DCGM_FI_DEV_(GPU_TEMP|XID_ERRORS|GPU_UTIL|FB_USED) '
```

**Fail-closed check:** `DCGM_FI_DEV_XID_ERRORS` and `DCGM_FI_DEV_GPU_TEMP` MUST appear in that output, or the
`GpuXidError` / `GpuHighTemp` alerts are blind. If `XID_ERRORS` is missing from the default field set, add it to
the exporter's metrics CSV and restart before proceeding.

## #2 — Prometheus scrapes the off-cluster target (verify)

The static `dcgm-exporter-rogueone` job (`192.168.1.230:9400`) lands via Argo sync of
`kube-prometheus-stack-values.yaml`. Confirm it is UP:

```
[mother] kubectl exec -n monitoring sts/prometheus-monitoring-kube-prometheus-prometheus -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/targets?state=active' | grep -o '"job":"dcgm-exporter-rogueone"[^}]*"health":"[a-z]*"'
```

Expected: `health":"up"` (while rogueone is awake — a sleeping laptop shows `down`, which is expected; it has no
dedicated down alert, but the blanket `TargetDown` net will page on a long sleep, same as the ray-worker target).

## #3 — Grafana dashboard + alerts (eyes-on UAT)

- Grafana → **rogueone GPU (DCGM)** (uid `dcgm-exporter`): the util / VRAM / temp / power / clocks panels populate
  and "Last Xid error" reads `none` on a healthy GPU.
- Alerting → the `dcgm-gpu` rule group shows `GpuXidError` (critical) and `GpuHighTemp` (warning) as `Normal`.

**UAT (the eyes-on part):** kick a training run (Ray / genre-trainer) and watch util/VRAM/temp/power move on the
dashboard in real time — the point is confirming the panels reflect a real workload, not just that the target is up.
