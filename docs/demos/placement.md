# Demo — placement inventory (B198)

Where every workload in the lab runs, what state it holds, whether it can move, and where it goes when the Strix
Halo box lands (B134) — and the two checks that keep that answer true. Sequence diagram:
[../diagrams/flow-placement.md](../diagrams/flow-placement.md). Runbook:
[../runbooks/observability.md](../runbooks/observability.md#placement-inventory--placementyaml-and-its-checks-b198-2026-09-27).

**Status: PARTIAL (2026-09-28) — UAT pending.** Repo and live checks run clean, every failure mode was drilled live, and
the in-cluster `placement-coverage` Job (runbook command) returned `OK — placement.yaml: 195 rows, live check clean.`
Open: the three eyes-on UAT steps below (DoD Pillar 3 — a green check is not a human looking).

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

Grafana 13, about 3 minutes. rogueone must be awake (it is the machine you are on).

**Open Explore**
1. Go to `https://grafana.weyland.lab` and sign in (Keycloak).
2. In the left menu, click **Explore** (the compass icon). If the menu is collapsed, click the ☰ icon at the top left
   first.
3. At the top left of the query pane, open the data-source dropdown and choose **Prometheus**.
4. On the query row, find the **Builder | Code** toggle on the right and click **Code**. A single text box appears.
5. Under the text box, open **Options** and set **Type** to **Instant**. (Instant gives one row per series in a table;
   Range would draw a graph instead.)

For each check: clear the text box, paste the query, press **Shift+Enter** (or click **Run query** at the top right),
then read the **Table** panel below.

**Check 1: Prometheus is scraping rogueone's exporter**
```
up{job="systemd-rogueone"}
```
Confirm: exactly **1 row**; `instance` is `192.168.1.230:9100`, `host` is `rogueone`; **Value = 1**.
A 0, or no rows, fails the check (the exporter is down or unreachable).

**Check 2: the exporter reports a real lab service as running**
```
node_systemd_unit_state{job="systemd-rogueone",state="active",name="rag-embed.service"}
```
Confirm: exactly **1 row**; `name` is `rag-embed.service`, `state` is `active`, `type` is `simple`; **Value = 1**.
A 0 means the service is not active on rogueone right now.

**Check 3: the nightly check exists in the cluster**
```
kube_cronjob_created{cronjob="placement-coverage"}
```
Confirm: exactly **1 row**; `namespace` is `monitoring`, `cronjob` is `placement-coverage`. The **Value is a large
number** (e.g. `1790566521`): the CronJob's creation time in Unix seconds, not a 1. Any value passes; no rows fails.

Reply with pass/fail for each (or a screenshot of the three tables).

## Teardown

Read-only: the checks read files and Prometheus. The drills above used temporary copies of `placement.yaml`; nothing
to remove.
