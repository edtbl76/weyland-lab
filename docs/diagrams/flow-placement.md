# Flow — placement inventory check (B198)

How `placement.yaml` stays true. On every push, `repo-guards` runs the repo check against the file and the LikeC4
model. Every night at 03:40 NY the `placement-coverage` CronJob runs the live check: it reads three families of series
from Prometheus (Kubernetes workloads from kube-state-metrics, Proxmox guests from pve-exporter, rogueone's active
systemd units from its systemd-only node-exporter over the last 24h) and compares them with the rows. Anything
running without a row, or a row naming nothing running, fails the Job and pages. Operate:
[runbooks/observability.md](../runbooks/observability.md#placement-inventory--placementyaml-and-its-checks-b198-2026-09-27).

```mermaid
sequenceDiagram
    participant G as repo-guards (every push)
    participant F as placement.yaml
    participant L as LikeC4 model
    participant C as placement-coverage CronJob (03:40 NY)
    participant P as Prometheus
    participant K as kube-state-metrics
    participant V as pve-exporter
    participant R as rogueone node-exporter (systemd only)
    participant AM as Alertmanager to Telegram
    G->>F: read rows (schema, enums, known hosts)
    G->>L: every node and host-native component has a row
    G-->>G: exit 0 clean, 1 drift named, 2 unreadable
    K->>P: kube_deployment/statefulset/daemonset/cronjob_created
    V->>P: pve_guest_info
    R->>P: node_systemd_unit_state (services and timers)
    C->>F: read the embedded copy (byte-identical, asserted in bats)
    C->>P: four kube_*_created queries
    C->>P: pve_guest_info
    C->>P: last_over_time unit state, 24h (rogueone sleeps)
    alt every source answered
        C->>C: running minus rows, rows minus running (on_demand and declared rows skipped)
        alt no difference
            C-->>C: exit 0
        else drift
            C-->>AM: Job fails, ScheduledJobFailed names the CronJob
        end
    else a source is empty or unreachable
        C-->>AM: exit 2, Job fails, never a pass
    end
```
