# Demo — DataHub catalog coverage (B158-A): the data-estate govern-by-CI guard

The mesh governs its INFRASTRUCTURE by CI — every metric-emitting workload is scraped
(`servicemonitor-coverage`), visualized (`dashboard-coverage`), alerted (`alert-coverage`). None of it
reached the DATA estate. `scripts/check-datahub-coverage.sh` closes that: it fails when a mesh dataset that
exists in Trino was never emitted to DataHub. Flow: [flow-datahub-coverage.md](../diagrams/flow-datahub-coverage.md).

## The point

Reconcile two planes; a table in the first but not the second is drift:

| Plane | Source |
|---|---|
| REALITY | the `iceberg.datasets_*.*` silver/gold + `iceberg.dbt.mart_*` tables Trino exposes |
| CATALOGED | the dataset URNs DataHub GMS holds (`scrollAcrossEntities`) |

## CLI walkthrough (the test — RUN against live infra)

From a box that can reach the cluster (rogueone), via port-forwards + the DataHub token:

```
kubectl -n data-mesh port-forward svc/trino-noauth 18200:8080 &
kubectl -n data-mesh port-forward svc/datahub-datahub-gms 18201:8080 &
TOKEN=$(kubectl -n weyland get secret datahub-token -o jsonpath='{.data.token}' | base64 -d)

TRINO_HTTP=http://localhost:18200 DATAHUB_GMS_URL=http://localhost:18201 DATAHUB_GMS_TOKEN="$TOKEN" \
  bash scripts/check-datahub-coverage.sh --list   # every mesh table + cataloged/UNCATALOGED
TRINO_HTTP=http://localhost:18200 DATAHUB_GMS_URL=http://localhost:18201 DATAHUB_GMS_TOKEN="$TOKEN" \
  bash scripts/check-datahub-coverage.sh           # the gate
```

RUN 2026-09-05 — the gate:

```
OK — all 111 mesh table(s) in Trino are catalogued in DataHub.
```

**The two bugs only a live run found** (the small bats fixtures could not — they let `awk` finish before
`grep -q` short-circuits): Trino's `nextUri` came back on its own in-cluster host (now re-pointed at the
endpoint given); and `awk | grep -Fxq` under `set -o pipefail` returned a **real match as no-match** (grep
short-circuits → awk dies with SIGPIPE → pipefail surfaces the 141), so the awk output is captured to a
variable first. Before that fix the guard reported **97/111 uncatalogued**; after it, the true **0 drift**.

**The negative cases — prove the guard can actually fail** (the bats suite, `scripts/tests/datahub-coverage.bats`, 12 cases):

```
# drift → exit 1
TRINO_TABLES="datasets_finance.price_daily
datasets_finance.filings_text" DATAHUB_URNS="iceberg.datasets_finance.price_daily" \
  bash scripts/check-datahub-coverage.sh ; echo $?   # 1, names filings_text

# GMS unreachable (empty catalogued set while Trino non-empty) → FAILS CLOSED, exit 2, not "all drift"
TRINO_TABLES="datasets_finance.price_daily" DATAHUB_URNS="" \
  bash scripts/check-datahub-coverage.sh ; echo $?   # 2
```

## UI walkthrough (eyes-on)

1. Open **https://datahub.weyland.lab** (Keycloak SSO).
2. Browse **Datasets → by platform → iceberg**.
   **UAT — confirm:** every `datasets_finance.*` / `datasets_health.*` / `datasets_music.*` silver table and
   every `dbt.mart_*` the guard listed as `cataloged` is present here with a domain + data product attached.
   The guard's job is that this stays true without anyone having to look.

## Teardown

Read-only — one Trino query + a paged GMS read + a set diff; no data created (kill the two port-forwards).
In the cluster it runs as the nightly `datahub-coverage` CronJob (03:05 NY), failure → Telegram via the
existing `ScheduledJobFailed` rule.
