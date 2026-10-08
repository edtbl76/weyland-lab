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

**3. Wake, wait, park: the live drill.** RUN 2026-10-01/02 and recorded in the runbook's Parked stores section:
`wake cockroachdb` changed one line; after the push, `wait` reported `Ready (1/1)` about 4 minutes after Argo applied
it. The data survived parking (`brfss.brfss_2020` 212,705 rows). `park` plus a push then gave `parked (0/0)`. While it
started, `CockroachdbDown` stayed pending, not firing, because the rule compares running to desired replicas.

**4. The alerts behave as measured.** promtool replays them in CI: `scripts/tests/alert-rules.bats`, `parked-store-
alerts.bats`, and `store-park.bats` (23 cases, all passing 2026-10-08). `NodeMemoryThrashing` fires on memory-stall
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
A woken store is parked again with `store-park.sh park <store>`, a push and `wait`. The checks write nothing.
