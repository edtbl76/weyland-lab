# Demo — placement inventory (B198)

Where every workload in the lab runs, what state it holds, whether it can move, and where it goes when the Strix
Halo box lands (B134) — and the two checks that keep that answer true. Sequence diagram:
[../diagrams/flow-placement.md](../diagrams/flow-placement.md). Runbook:
[../runbooks/observability.md](../runbooks/observability.md#placement-inventory--placementyaml-and-its-checks-b198-2026-09-27).

**Status: DONE (2026-09-28).** Repo and live checks run clean, every failure mode was drilled live, the in-cluster
`placement-coverage` Job returned `OK — placement.yaml: 195 rows, live check clean.`, the owner passed the UAT
eyes-on in Grafana, and CI #201 passed every step including the SonarQube gate.

| Live check (2026-09-27) | Result |
|---|---|
| Rows | 195 — 158 Kubernetes workloads, 25 rogueone services/timers, 3 user timers + 7 declared tools, 2 Proxmox guests |
| kube-state-metrics vs `kubectl` | 121 Deployments, 13 StatefulSets, 3 DaemonSets, 21 CronJobs — identical |
| rogueone exporter | systemd collector only; 1,160 `node_systemd_unit_state` series; job `systemd-rogueone` up; 118 active services + timers |
| Repo check | `OK — 195 rows, repo check clean` |
| Live check | `OK — 195 rows, live check clean` (exit 0) |
| Drill: a k8s row removed (trino) | exit 1, `running with no row` + a row to paste |
| Drill: a row for a workload that does not exist | exit 1, `row names something that is not running` |
| Drill: a rogueone service row removed (ollama) | exit 1, names `systemd:rogueone/ollama.service` |
| Drill: a rogueone row for a unit that is not running | exit 1, names it |
| Drill: rogueone silent for 24h (wrong exporter port) | exit 2, `no systemd series ... in the last 24h` |
| Drill: Prometheus unreachable | exit 2 |
| First in-cluster Job (2026-09-28, runbook command) | ran end to end in `monitoring`; exit 1 naming `systemd-hostnamed.service` — a stock D-Bus-activated unit, active only briefly, that the exporter's first hours had not seen. Added to `host_os_units`; a 15-day `max_over_time` sweep found no other uncovered unit |
| Second in-cluster Job (2026-09-28) | exit 1 naming `flatpak-system-helper.service` — another on-demand helper. Root cause, not another row: the check counted any unit active at ANY moment in 24h. Fixed to "active in > 50% of the host's samples" (measured: real services/timers 1.0, the two helpers 0.017 / 0.006); live check clean, the three rogueone drills re-run and still fail correctly |

## CLI walkthrough

Repo check (what `repo-guards` runs):

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-placement.sh
```
Expect `OK — placement.yaml: <N> rows, repo check clean.`

The Strix Halo migration table:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-placement.sh --migration
```
Expect a table with Trino and `rag-embed` as `k3s-worker`, `whisper` as `tbd`, and a summary line of counts.

Live check, in-cluster (what the CronJob runs nightly):

[mother]
```
kubectl -n monitoring create job placement-coverage-now --from=cronjob/placement-coverage && kubectl -n monitoring wait --for=condition=complete job/placement-coverage-now --timeout=300s; kubectl -n monitoring logs job/placement-coverage-now; kubectl -n monitoring delete job placement-coverage-now
```
Expect `OK — placement.yaml: <N> rows, live check clean.`

rogueone's exporter answering:

[rogueone]
```
curl -s localhost:9100/metrics | grep -c '^node_systemd_unit_state'
```
Expect a count in the thousands and no `node_filesystem_` lines.

## UI walkthrough (UAT)

**Open this link** (signed in to Grafana through Keycloak). It opens Explore with all three checks already run:

[UAT — placement checks in Grafana Explore](https://grafana.weyland.lab/explore?schemaVersion=1&orgId=1&panes=%7B%22uat%22%3A%7B%22datasource%22%3A%22prometheus%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22up%7Bjob%3D%5C%22systemd-rogueone%5C%22%7D%22%2C%22instant%22%3Atrue%2C%22range%22%3Afalse%2C%22editorMode%22%3A%22code%22%2C%22format%22%3A%22table%22%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22prometheus%22%7D%7D%2C%7B%22refId%22%3A%22B%22%2C%22expr%22%3A%22node_systemd_unit_state%7Bjob%3D%5C%22systemd-rogueone%5C%22%2Cstate%3D%5C%22active%5C%22%2Cname%3D%5C%22rag-embed.service%5C%22%7D%22%2C%22instant%22%3Atrue%2C%22range%22%3Afalse%2C%22editorMode%22%3A%22code%22%2C%22format%22%3A%22table%22%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22prometheus%22%7D%7D%2C%7B%22refId%22%3A%22C%22%2C%22expr%22%3A%22kube_cronjob_created%7Bcronjob%3D%5C%22placement-coverage%5C%22%7D%22%2C%22instant%22%3Atrue%2C%22range%22%3Afalse%2C%22editorMode%22%3A%22code%22%2C%22format%22%3A%22table%22%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22prometheus%22%7D%7D%5D%2C%22range%22%3A%7B%22from%22%3A%22now-15m%22%2C%22to%22%3A%22now%22%7D%7D%7D)

Pass (Raw or Table view, one result series per query):

| Query | Pass |
|---|---|
| A `up{job="systemd-rogueone"}` | `instance="192.168.1.230:9100"`, `host="rogueone"`, value **1** |
| B `node_systemd_unit_state{…name="rag-embed.service"}` | `state="active"`, `type="simple"`, value **1** |
| C `kube_cronjob_created{cronjob="placement-coverage"}` | `namespace="monitoring"`; the value is the CronJob's creation time in Unix seconds (any value passes) |

**Passed 2026-09-28 (owner, eyes-on):** A = 1, B = 1, C = 1790566521 in `monitoring`.

If the link lands on the Grafana home page instead of Explore, your Grafana role is below Editor: Explore needs
`datasources:explore`. That was the case until 2026-09-28 (the SSO role-mapping fix in
`k8s/monitoring/kube-prometheus-stack-values.yaml`); sign out and back in after a role change.

## Teardown

Read-only: the checks read files and Prometheus. The drills above used temporary copies of `placement.yaml`; nothing
to remove.

## Host units and host config files (B180)

The systemd units and host config files on mother, rogueone and the whisper LXC are rows in `placement.yaml` too:
unit rows carry `source` (repo copy), `path` (installed location) and, for a timer, `every`; drop-ins, `/etc` configs,
apparmor and the whisper shim sit under `host_config:`. The host check reads each host over its `access` path and
runs nightly inside `machine-inv-drift` (03:45 NY), whose Kuma heartbeat goes down on any finding.

**Status: DONE (2026-10-01).** Host check clean on all three hosts; every drill below failed the way it should; the
nightly job's dry run ran the host check inside itself; the Port read-back matched on all three hosts; CI #216 passed
every step including the SonarQube gate (0 new issues, new-code coverage 85.9%), CI #217 green on the
final commit, and the owner passed the Port UAT.

| Run (2026-09-30, on a throwaway copy of the inventory — nothing on the hosts changed) | Result |
|---|---|
| Baseline | `OK — placement.yaml: 210 rows, hosts check clean.` exit 0 |
| Drill: a real line added to the repo copy of mother's `weyland-k3s.conf` | exit 1, `DRIFT at /etc/needrestart/conf.d/weyland-k3s.conf` |
| Drill: only a comment added to it | exit 0 — comment-only differences pass |
| Drill: the `restic-backup.timer` row removed | exit 1, `rogueone: unit restic-backup.timer is installed on the host but not in the inventory` |
| Drill: that timer's `every` set to 1m | exit 1, `timer stale — last fired 15h ago, every 1m` |
| Drill: mother's access pointed at a host that does not exist | exit 2, `gather failed (ssh: Could not resolve hostname ...)` — never a pass |
| Nightly job, dry run | `OK — placement.yaml: 210 rows, hosts check clean.` inside `machine-inv-drift.sh --dry-run` |
| Port | `verify` OK — mother 36, rogueone 882, weyland 742 `installed_package` entities, matching the inventory |

What the first run found (before the drills): the rogueone restic backup failing nightly since 09-25, the Ollama
`OLLAMA_HOST` drop-in with no repo copy, `weyland-image-prune` running mid-day (moved to 00:15 NY), and a
system/user timer-scope bug in the check itself. All fixed.

**Teardown:** none needed. The drills ran on throwaway copies of the inventory in a scratch directory; nothing on
the hosts was changed. The only live writes are the Port entities `emit` keeps in step with the inventory.

### CLI walkthrough

Host check (every host; exit 1 names each finding, 2 = a host could not be read):

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/placement_check.py --hosts --file /home/edwardmangini/IdeaProjects/weyland/placement.yaml
```
Expect `OK — placement.yaml: <N> rows, hosts check clean.`

The nightly job without side effects (no push, PR, Port write or Kuma ping):

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/machine-inv-drift.sh --dry-run
```
Expect the `hosts check clean` line before the `signal:` line.

### UI walkthrough (UAT) — Port

Signed in to Port, open each link:

1. [whisper-server.service in Port](https://app.port.io/installed_packageEntity?identifier=weyland--systemd-unit--whisper_whisper-server.service)
   — pass: the title reads `whisper/whisper-server.service (systemd-unit)` and Details shows **Host** `weyland`.
2. [mother's needrestart config in Port](https://app.port.io/installed_packageEntity?identifier=mother--host-config--_etc_needrestart_conf.d_weyland-k3s.conf)
   — pass: the title reads `/etc/needrestart/conf.d/weyland-k3s.conf (host-config)` and Details shows **Host** `mother`.
3. [Installed Packages](https://app.port.io/installed_packages) — pass: the table has **Kind** and **Status** columns
   and the result count equals the `emit` total (1660 on 2026-09-30).

Port's package page shows Title, dates and Host only; Kind and Status are columns on the list page (the kind is also in
the title).

**Passed 2026-10-01 (owner, eyes-on):** whisper-server.service → Host `weyland`; weyland-k3s.conf → Host `mother`;
Installed Packages 1660 results with Kind/Status columns.
