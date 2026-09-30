# Flow — placement inventory check (B198, host check B180)

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
    C->>P: unit active samples / host samples over 24h, keep above 0.5
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

**Host check (B180).** Nightly on rogueone, inside `machine-inv-drift` (03:45 NY), `placement_check.py --hosts` reads
every host over its `access` path and compares the installed unit and config files with their repo copies. The
result joins the machine-inventory result in one Kuma heartbeat.

```mermaid
sequenceDiagram
    participant D as machine-inv-drift (rogueone, 03:45 NY)
    participant F as placement.yaml (origin/main worktree)
    participant H as host (local, ssh mother, ssh weyland pct exec 103)
    participant G as repo copies (source)
    participant K as Uptime Kuma to Telegram
    D->>F: unit and host_config rows per host, with access
    D->>H: one bash gather per host
    H-->>D: F path and base64 content, U unit files, X failed units, T timer last trigger
    alt every host answered
        D->>G: read each row's source
        D->>D: compare ignoring comment lines, unlisted units, failed units, timers older than 2x every
        alt no finding
            D-->>K: up (when the machine inventory is also clean)
        else findings
            D-->>K: down, placement host drift
        end
    else a host could not be read
        D-->>K: down, placement host check could not read
    end
```
