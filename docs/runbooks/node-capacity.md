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

**What it is NOT:** with swap disabled, the node does not silently degrade — it either has headroom or
the kernel OOM-kills the largest offender. If a pod died, that's the backstop working, not a bug.
Trace which cgroup was killed with `journalctl -k | grep -i oom_memcg` on mother.

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
