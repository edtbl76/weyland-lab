# Node Capacity — mother RAM ceiling & the store-park discipline

**Why this exists:** mother is a single k8s node whose always-on data-mesh fleet sits at a resident
baseline of **~69 GiB**. The host it lives on (weyland, MS-A2) has a hard physical ceiling, and
**neither host nor guest has swap** (disabled in B99 — see [hosts.md](../hosts.md) mother row: swap
thrashed the control plane into the 2026-07-21 outage; the intended failure mode is clean kernel-OOM).
So there is very little slack, and any job that adds a few GiB (a dataset hydrate, a heavy Superset
query, a DataHub reindex) can tip the node into memory pressure. That presents as "mother is
misbehaving" — UIs go sluggish, kubectl lags — when in fact **nothing is stuck; the node is simply
full.**

## The hard ceiling

| Layer | RAM | Notes |
|---|---|---|
| **weyland** (Proxmox host, MS-A2) | **91 GiB usable** (96 GB physical; ~5 GB firmware/iGPU reserved) | **No swap.** Only VM is mother. |
| Host + KVM overhead | **~10 GiB** | Proxmox services + the KVM process for mother's guest pages. |
| **mother** (vm-101) allocation | **78 GiB** (79872 MB) as of **2026-08-07** (bumped 72→78) | **No swap** (B99). Cold resize only — no balloon/hotplug device. |
| **mother safe max** | **~80 GiB** | Past this the host itself risks OOM (no host swap = hard crash). Do **not** exceed ~80 GiB. |
| Always-on fleet baseline (guest) | **~69 GiB** | The floor the running data-mesh stores hold at rest. |

**Bottom line:** the RAM bump is a small relief valve (~9 GiB of guest headroom over the ~69 GiB
baseline), not a fix for oversubscription. The host is the wall. The durable lever is parking idle
stores.

## The real lever — park idle Tier-2 stores

When the node is tight, free headroom by sleeping data-mesh stores you're not actively using, via the
**store-scaler easy button** (Port self-service → port-agent → `store-scaler` — see
[port-agent-easy-button.md](port-agent-easy-button.md)). The heaviest resident stores (from
`kubectl top pods -A --sort-by=memory`) and roughly what parking each returns:

| Store | ~Resident | Park when… |
|---|---|---|
| cassandra-0 | ~3.6 GiB | not querying wide-column datasets |
| opensearch (×2: `opensearch` + `data-mesh`) | ~4.1 GiB | not running search/OpenSearch ingest |
| mongodb | ~1.8 GiB | not querying document datasets |
| superset-worker | ~2.0 GiB | no BI dashboards open |
| clickhouse / neo4j / weaviate | ~1.3–1.8 GiB each | idle |

Parking cassandra + both opensearch + mongodb + superset-worker alone returns **~11 GiB** — more than
the whole RAM bump. **Sleep is STICKY-parked against Argo selfHeal** — see the easy-button runbook.

## Diagnosing a "misbehaving mother" (stuck vs. full)

Run in order — **mother:**
```
free -h; ps -eo pid,rss,args --sort=-rss | grep -c execute_step
```
- `available` near 0 with **no** single runaway → **full, not stuck.** No process to kill; free
  headroom by parking stores (above) or wait for the running job to finish.
- `execute_step` count **> 2** → overlapping Dagster hydrate runs (kill the stale one; hydrates are
  capped at `max_concurrent=2` — see [schedules.md](../schedules.md)).

```
kubectl get nodes; kubectl describe node mother | grep -A6 Conditions
kubectl top pods -A --sort-by=memory | head -15
```
- Node `Ready`, all Conditions `False`, but top pod only a few GiB and the total is spread across the
  fleet → **aggregate saturation** (the baseline crept up), not a leak. There is nothing to "fix" at
  the process level — this is a capacity-shape problem.

**Correction (B199, 2026-10-01): with swap disabled the node DOES silently degrade.** It cannot page anonymous
memory out, so under pressure the kernel evicts and re-reads *file-backed* pages (binaries, JARs, mmapped data) —
a page-cache thrash that freezes the whole node, k3s included, **without an OOM kill and without a log line**. The
OOM backstop only fires when even that fails. If a pod died, check `journalctl -k | grep -i oom_memcg` on mother;
if nothing died but the node went silent, it was the thrash below.

## The two freeze alerts (B199, 2026-10-02)

The generic threshold alerts (`NodeMemoryCritical` > 95% used, the built-in `NodeMemoryHighUtilization` > 90%) fired
~57 times in 13 days and became background — and the freeze itself never reported, because Prometheus runs ON mother
and freezes with it. Two specific alerts in `k8s/monitoring/node-memory-alerts.yaml`:

| Alert | Fires when | Why that threshold |
|---|---|---|
| `NodeMemoryThrashing` (critical) | tasks stall on memory (PSI `node_pressure_memory_waiting`) > 10% of the time for 2 min | 17.2% at the 09-30 freeze, 6.1% at the busiest pre-park midday, 2.5% on a parked night |
| `NodeFroze` (warning) | node-exporter missed 2+ of its 10 samples in 5 min (≥ ~60-90s of silence), seen after recovery | records every freeze, once — the count the 7-night acceptance needs |

Replayed over 13.5 days of history: `NodeMemoryThrashing` would have fired **4 times, each at a real freeze** (09-21
02:43, 09-26 07:36, 09-29 01:01, 10-01 02:36) and never otherwise; `NodeFroze` **17 times, one per freeze episode**.
Behaviour is pinned by promtool unit tests on the real rule text (`scripts/tests/alert-rules.bats`, fixtures in
`scripts/tests/fixtures/alert-rules/`), run in CI's shell-tests step (Alpine `prometheus` = promtool).

**When `NodeMemoryThrashing` pages:** something just pushed mother over — check what started in the last minutes
(a CI run, a CronJob, a woken store), and free memory: `bash scripts/store-park.sh park <store>` + push, or stop the job.
**When `NodeFroze` pages:** a freeze already happened and recovered; look at MemAvailable and `pgmajfault` around it.

**Night check (B199's 7-night acceptance)** — Grafana → Explore → Prometheus (agents: the Grafana MCP
`query_prometheus`), each an INSTANT query at the night's end, 07:00 NY = `T11:00:00Z` (EDT; `T12:00:00Z` in EST):

| Check | PromQL | Clean |
|---|---|---|
| Lowest free memory (GB) | `min_over_time(node_memory_MemAvailable_bytes{instance="192.168.1.243:9100"}[7h]) / 1e9` | no collapse (nights 1-6: 5.1–9.1) |
| No scrape gap (= no freeze) | `count_over_time(node_memory_MemAvailable_bytes{instance="192.168.1.243:9100"}[7h])` | **840** (7 h × 2/min) |
| Never NotReady | `min_over_time(kube_node_status_condition{node="mother",condition="Ready",status="true"}[7h])` | 1 |
| Memory-stall peak | `max_over_time(rate(node_pressure_memory_waiting_seconds_total{instance="192.168.1.243:9100"}[2m])[7h:1m])` | < 0.10 (`NodeMemoryThrashing`'s line) |

Plus the 01:00 `nightly-images` run did not die of memory (`woodpecker-cli pipeline ls`; a code-gate failure is not a
stall). Check the conditions, not `ALERTS`: neither alert has ever fired through Prometheus, so "no alert" alone cannot
tell a clean night from a broken rule. Tally: `docs/backlog.md` B199.

## Telegram noise (B199, 2026-10-02)

3,618 Telegram messages in 14 days (~258/day; Alertmanager received 169,142 alert posts) — the volume that buried
real pages, including 13 days of no MinIO backup. Measured by rebuilding each `(alertname, namespace)` group's
messages from `ALERTS` history (fire + 4h repeats + membership changes + resolve) against
`alertmanager_notifications_total{integration="telegram"}`:

| Source | 14-day msgs | Fix |
|---|---|---|
| `dagster-freshness-check` (`*/30`) posted alerts with no `endsAt` → auto-resolved in 5m → a NEW firing+resolved pair every run (~96/day per stuck job) | ~2,400 | `endsAt` 45m ahead: one continuous alert, 4h repeats, one resolve (`k8s/dagster/freshness.yaml`, tested in `dagster-freshness.bats`) |
| Built-ins `NodeMemoryMajorPagesFaults` + `NodeMemoryHighUtilization` | ~287 | disabled (`defaultRules.disabled`) — replaced by `NodeMemoryThrashing` / `NodeFroze` |
| `InfoInhibitor` (must never notify; the values file's route tree dropped the chart's null route) | 40 | routed to `null` (amtool route test) |

Kept on purpose: the three daily synthetic posters (auto-resolve = 2 msgs/day; persistent would add 4h repeats);
`KubeJobFailed` (covers every Job — `ScheduledJobFailed` lists only 20); `NodeMemoryRequestsNearCeiling` (requests,
not usage). Open: `LiteLLMEgressEnabled` / `BifrostSpendObserved` page every 4h about deliberate states (owner call).

## Parked stores (B199, 2026-10-01 — undo with B134 when hardware lands)

**Parked by default** (`replicas: 0` committed to git; Argo enforces it, so a live scale is reverted within ~3 min):

| Workload | ~Returns | Manifest |
|---|---|---|
| Cassandra | ~3.8 GB | `k8s/data-mesh/cassandra.yaml` (StatefulSet) |
| MongoDB | ~1.8 GB | `k8s/data-mesh/mongodb.yaml` |
| CockroachDB | ~1.3 GB | `k8s/data-mesh/cockroachdb.yaml` |
| Superset Celery worker | ~2.1 GB | `k8s/superset/superset-values.yaml` → `supersetWorker.replicas.replicaCount` |

**ClickHouse is NOT parked** — Langfuse uses it as its live trace store (`k8s/langfuse/langfuse.yaml`).

**Wake one** (e.g. to run a hydrate job or a notebook against it) — the script edits the one line in git; you push:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/store-park.sh wake cockroachdb
```
Push the file it names, then wait until it is really Ready (exit 0 = Ready, 1 = not there within 10 min, 2 = could
not ask the cluster):

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/store-park.sh wait cockroachdb
```
`wake` and `park` also **resume / pause the store's DataHub ingestion schedule** in the same command (via
`scripts/datahub_schedule.py`: a temporary port-forward to GMS and the token from the cluster Secret
`weyland/datahub-token`, never printed; every change is read back, and `status` prints a config fingerprint so you can
see the recipe came through untouched). **Park it again** the same way with `park` (then push and `wait`). `status` shows every store's git setting next to
what is running; `all` works in place of a store name. Stores: `cassandra`, `mongodb`, `cockroachdb`,
`superset-worker`. Tested in `scripts/tests/store-park.bats`. The store-scaler easy button does NOT stick (selfHeal
reverts a live scale) — git is the only switch. While parked:
- Its Down alert stays silent — the alerts compare running to DESIRED replicas (`scripts/tests/parked-store-alerts.bats`).
- Its DataHub ingestion schedule is paused (by `store-park.sh`) and the source is listed as parked in the ingestion
  watchdog (`scripts/datahub_ingestion_check.py` PARKED).
- The daily `datahub_catalog_emit_job` logs a warning for the CockroachDB profile step and carries on.
- On-demand Dagster hydrate jobs that write to it (`weyland_datasets_{music,health,finance}_hydrate_job`,
  `weyland_aidlc_kb_job` for Mongo) need the store woken first.

**Undo** when the new hardware lands: the checklist is in `docs/backlog.md` B134 § "Undo on hardware" (EMA-195).

**Tested live 2026-10-01/02 (wake → Ready → data intact → park → parked):** `store-park.sh wake cockroachdb` changed
one line; after the push, `wait` reported `Ready (1/1)` ~4 min after Argo applied it (Argo itself takes up to ~3 min —
`argocd app sync data-mesh` skips that); the data survived parking (`brfss.brfss_2020` 212,705 rows,
`nhis.nhis_adult_2022_adult22` 27,651, `company_financials` 20,741); `park` + push → `wait` reported `parked (0/0)`.
Alerts: `CockroachdbDown` was **pending** (never firing) for 3.5 min while the woken pod started — the new rule doing
its job; it fires only if a woken store is not Ready within 5 min. The four parked stores freed memory immediately:
MemAvailable 2.7–6 GB → **12.0 GB**, pod working set 72 → 66 GB.

**DataHub schedules, live 2026-10-02:** `park all` paused `Cassandra - Weyland` (was `15 4 * * 0`), `MongoDB - Weyland`
(`45 3 * * *`) and `CockroachDB - Weyland` (`30 3 * * *`), each read back. A live `wake cockroachdb` → `park cockroachdb`
round trip restored then re-paused the exact schedule with the config fingerprint unchanged (`7b77707637c5`) throughout.

## The overnight stalls (B199, measured 2026-10-01)

**27 node-wide freezes of 1–3 minutes in 13 days** (2026-09-18 → 10-01), found as gaps in mother's node-exporter
samples. During each, every journal stops, k3s misses its own heartbeats and every API watch errors, Woodpecker
expires the running CI task (pipelines show `killed`), and once (09-30 02:44 NY) the node went `NotReady`.

| What | Value |
|---|---|
| Pod working set, any night | **72–75 GB of 78 GB** — `weyland` ~30.5 GB, `data-mesh` ~30.4 GB; no single dominant pod (top 25 are 1–5 GB) |
| "Calm" state | MemAvailable 4–6 GB, yet **500–1,400 MB/s disk reads and ~1,000–1,700 major faults/s** — already thrashing |
| At the tip | major faults 9,000–17,000/s, disk reads 1.6–2.8 GB/s, load1 350–590, memory stall 14% → freeze |
| CPU / IO-device pressure | low throughout — this is memory, not disk or CPU |

**Triggers are incidental** — whatever adds the last few hundred MB: a CI step pod (+0.8–2.3 GB; the 00:40–01:13
cluster), the 03:25 `pr-lifecycle-reconcile` CronJob starting (03:25 on 09-25/26/27/30, with 5–6 GB "free"),
the 01:00 nightly-images build. Moving a trigger moves the stall; it does not remove it. The cause is the
baseline. Timeline query (port-forward `svc/monitoring-kube-prometheus-prometheus` and scan
`node_memory_MemAvailable_bytes{instance="192.168.1.243:9100"}` at a 30s step for gaps ≥ 60s).

## Resizing mother's RAM (procedure)

Cold resize only (no hotplug). This is a **full-cluster blip** — mother is the single k8s node, so
every pod restarts on boot (a few minutes). **weyland (Proxmox host):**
```
qm shutdown 101 --timeout 180
```
```
qm status 101
```
Once `stopped` (if it hangs past the timeout: `qm stop 101`):
```
qm set 101 --memory <MB>
```
```
qm start 101
```
**Never set `<MB>` above ~81920 (80 GiB)** — the host has no swap and needs ~10 GiB for itself.

Verify — **mother:**
```
free -h; kubectl get nodes; kubectl get pods -A | grep -Ev 'Running|Completed'
```

## Related
- [hosts.md](../hosts.md) — mother row: swap-disabled (B99) + kubelet reserved/eviction backstop.
- [port-agent-easy-button.md](port-agent-easy-button.md) — the store-scaler park/wake mechanism.
- [schedules.md](../schedules.md) — overnight-only auto-runs + hydrate `max_concurrent=2` (keeps big
  jobs off the node during the day).
