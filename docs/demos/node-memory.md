# Demo: keeping mother out of overnight memory stalls (B199)

mother used to stall overnight: memory ran out, the node stopped answering, and CI runs died with `task expired`. Idle
Tier-2 stores are now parked by default and switched only through git, two alerts catch a stall, and a written
nightly check proved seven clean nights in a row. Operating detail: [runbooks/node-capacity.md](../runbooks/node-capacity.md).
The CLI part was RUN on 2026-10-08 on rogueone unless a step says otherwise.

## Sequence diagram
See [../diagrams/flow-node-memory.md](../diagrams/flow-node-memory.md).

## CLI walkthrough

**1. What is parked.** `status` is read-only and shows git's setting next to what is running:
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/store-park.sh status
```
```
cassandra        git=0  live(desired/ready)=0/   datahub=paused  (config 286899f6bbda)
mongodb          git=0  live(desired/ready)=0/   datahub=paused  (config 35e042312e69)
cockroachdb      git=0  live(desired/ready)=0/   datahub=paused  (config 7b77707637c5)
superset-worker  git=0  live(desired/ready)=0/   datahub=-
```
CockroachDB's DataHub config fingerprint is the same one recorded at the 2026-10-02 round trip, so parking has not
altered the recipe.

**2. Negative: an unknown store is refused, exit 2.** Nothing is edited:
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/store-park.sh wake not-a-store
```
```
unknown store 'not-a-store' — one of: cassandra mongodb cockroachdb superset-worker (or all)
```

**3a. One command each way (B232, 2026-10-24).** `up` replaces wake, push, wait; `down` replaces park, push, wait.
Each commits only the store's manifest and pushes it, so **the owner runs it** (an agent hands over the command):
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/store-park.sh up cockroachdb
```
RUN 2026-10-24 by the owner on rogueone, one command each way:
```
cockroachdb: replicas 0 -> 1 in nodes/mother/lab/weyland-platform/k8s/data-mesh/cockroachdb.yaml
pushed: store-park: up cockroachdb (replicas 1)
CockroachDB - Weyland: schedule changed -> 30 3 * * * America/New_York
cockroachdb: waiting — git wants 1, cluster has desired=0 ready=0 — Argo has not applied the push yet (…)
…  (7 lines while Argo polled, then 7 with desired=1 ready=0 while the pod started)
cockroachdb: Ready (1/1)
```
```
cockroachdb: replicas 1 -> 0 in nodes/mother/lab/weyland-platform/k8s/data-mesh/cockroachdb.yaml
pushed: store-park: down cockroachdb (replicas 0)
CockroachDB - Weyland: schedule changed -> paused
…  (10 lines while Argo polled)
cockroachdb: parked (0/0)
```
The two commits on `origin/main`, `4c6401b9` (up) and `282b754a` (down), each hold exactly one file,
`k8s/data-mesh/cockroachdb.yaml`. Afterwards `status` showed every store `git=0`, `0/`, DataHub `paused`, with
CockroachDB's config fingerprint still `7b77707637c5` (the recipe untouched). Most of each run was Argo's poll
(about 3.5 min), so `up`/`down` now ask Argo to sync right after the push (an `argo: sync of data-mesh requested …`
line; with the CLI session or the sync-only `store-park` token, never the admin password; best effort, falling back
to the poll; 45 bats cases in all).

RUN 2026-10-24 again by the owner, with the sync (both paths ran live):
```
pushed: store-park: up cockroachdb (replicas 1)
argo: sync of data-mesh requested (CLI session)
cockroachdb: waiting — git wants 1, cluster has desired=0 ready=0 — …        (1 line; Argo applied it at the next check)
…  (7 lines with desired=1 ready=0 while the pod started)
cockroachdb: Ready (1/1)
```
```
pushed: store-park: down cockroachdb (replicas 0)
argo: sync of data-mesh requested (store-park token)
cockroachdb: waiting — git wants 0, cluster has desired=1 ready=1 — …        (1 line)
cockroachdb: parked (0/0)
```
Argo now applies the push within one 30-second check instead of about 3.5 minutes; `down` went from about 5 minutes to
under one, and what is left of `up` is the pod starting. `down` ran almost two hours later, after the CLI session had
expired, so it took the token path: Argo recorded that sync as `initiatedBy: store-park`. Commits `4e81e1bd` (up) and
`a76a1fd3` (down) each hold only `cockroachdb.yaml`; `status` afterwards: `git=0  0/  datahub=paused`, fingerprint
`7b77707637c5`. The run also showed the progress line still advising a manual sync after one was requested; it now
says `sync requested, Argo is applying the push`. The refusals (not on `main`; behind or
ahead of `origin/main`; cannot fetch; the manifest already edited) each exit 2 before any edit, and a rejected push
exits 2 with git's reason and the commit left local: 15 `up`/`down` cases in `store-park.bats`, run against real git
(a scratch repo with a bare origin), not a git stub.

**3. Wake, wait, park: the live drill.** RUN 2026-10-01/02 and recorded in the runbook's Parked stores section:
`wake cockroachdb` changed one line; after the push, `wait` reported `Ready (1/1)` about 4 minutes after Argo applied
it. The data survived parking (`brfss.brfss_2020` 212,705 rows). `park` plus a push then gave `parked (0/0)`. While it
started, `CockroachdbDown` stayed pending, not firing, because the rule compares running to desired replicas.

**4. The alerts behave as measured.** promtool replays them in CI: `scripts/tests/alert-rules.bats`, `parked-store-
alerts.bats`, and `store-park.bats` (23 cases, all passing 2026-10-08; 32 since B232's `up`/`down`, 2026-10-24). `NodeMemoryThrashing` fires on memory-stall
pressure above 10% for 2 minutes; replayed over 13.5 days it fired 4 times, all at real freezes. `NodeFroze` fires once
per scrape gap. A drill `NodeFroze` reached Telegram on 2026-10-02 (notifications sent 13,409 to 13,410, failed
unchanged).

**5. The seven-night soak.** The queries are in the runbook's Night check, run in Grafana Explore at 07:00 NY. Night 7
(10-07 to 10-08), RUN 2026-10-08:

| Check | Result | Clean when |
|---|---|---|
| Lowest free memory | 4.8 GB | no collapse (the seven nights: 4.8-9.1 GB) |
| Samples (no freeze) | 840 | 840 |
| Ready | 1 | 1 |
| Memory-stall peak | 0.030 | under 0.10 |
| 01:00 nightly | #288 success | finished with a code verdict |

All seven nights were clean.

## UI walkthrough (UAT, eyes on)
1. **Grafana:** Explore, then Prometheus. Run the runbook's Night check queries for any night; the numbers match the
   table above for 10-07 to 10-08.
2. **Grafana:** Alerting, then Alert rules. `NodeMemoryThrashing` and `NodeFroze` are listed and Normal.

## Expected result
- The four parked stores stay at 0 until someone wakes one through git; a woken store's Down alert waits 5 minutes
  before firing.
- A real stall pages through Telegram within about 2 minutes; a clean night shows the four checks inside their lines.

## Cleanup / teardown
A woken store is parked again with `store-park.sh down <store>` (one command: commit, push, wait; B232). The checks
write nothing.
