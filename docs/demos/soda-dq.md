# Demo — Soda data-quality scan → DataHub Assertions

> **Pending live end-to-end validation run.** The commands below are lifted from `runbooks/soda.md`; this
> demo-shaped walkthrough has **not** yet been executed straight through against live infra.

Soda Core runs an **independent contract scan** over the 7 dbt marts (`iceberg.dbt.mart_*`) — row presence, key
uniqueness/completeness, value-range bounds, and per-column **emptiness tripwires** — then pushes each check to
**DataHub as a `_NATIVE_` DATASET Assertion** on the mart's `trino` URN. It is Slice C of the L5
(Governance/Security) layer (Ranger + OPA + Soda). Complementary to dbt's in-transform tests: dbt validates
*during* the build (row-level, null-filtered); Soda validates the *published output* (aggregate) and so catches
all-NULL columns that dbt range checks pass vacuously. Grounded in [../runbooks/soda.md](../runbooks/soda.md).

**Where results land** (there is **no Soda web UI** — Soda Cloud is paid, $0 rule):
- **Dagster** run logs (`soda_quality_job`) — the `[PASSED]/[FAILED]` breakdown.
- **DataHub → each mart → Quality / Validations tab** — one assertion per check (via `emit_soda_assertions`).

**Sequence:** [flow-e2e-soda.md](../diagrams/flow-e2e-soda.md)

## Prerequisites

- **Dagster** — `https://dagster.weyland.lab` (Keycloak forward-auth). Code pod `deploy/dagster-user-code`
  (ns `weyland`). Soda lives in an **isolated venv** `/opt/soda-venv` inside that image; the op shells out to it.
- **dbt marts present** — the 7 `iceberg.dbt.mart_*` tables must exist (run [dbt.md](dbt.md) first). A model fix
  only takes effect after `dbt run` rebuilds the Trino-materialized table.
- **trino-noauth proxy** — `trino-noauth.data-mesh.svc.cluster.local:8080` (nginx strips the `Authorization`
  header). Soda's Trino connector **always** sends HTTP Basic auth; Trino (no authenticator) rejects a password
  over plaintext (`401 Password not allowed for insecure authentication`), so `configuration.yml` **must** point
  at the proxy — **not** `trino.data-mesh` directly.
- **DataHub GMS** reachable in-cluster (`datahub-datahub-gms.data-mesh.svc:8080`) for the assertion emit
  (non-fatal — a DataHub hiccup never masks a data-quality failure).
- Check files (COPY'd into the user-code image): `soda/configuration.yml`, `soda/checks/{music,health}.yml`.
- `kubectl` runs on **mother** (`emangini@mother`).

## UI walkthrough

1. Open `https://dagster.weyland.lab` → **Jobs** → **`soda_quality_job`** → **Launch Run** (the nightly
   `soda_quality_schedule` at 05:30 is **STOPPED by default** — enable it only once a manual run is green).
2. In the run view, read the op log: the `soda scan` output prints the `[PASSED]/[FAILED]` breakdown per check,
   then an `---EMIT---` marker and the assertion-emit result.
3. Open `https://datahub.weyland.lab` (Keycloak SSO) → navigate to a mart, e.g. `iceberg.dbt.mart_country_health`
   (trino platform) → **Quality** (Validations) tab → one `_NATIVE_` assertion per Soda check, each with its
   latest pass/fail run event.

## CLI walkthrough

Kubectl runs on **mother**.

**Confirm the marts exist first** (Soda scans published output, not the build):
```
[mother] kubectl -n data-mesh exec deploy/trino -- trino --execute "SHOW TABLES FROM iceberg.dbt"
```

**Scan only** — prints the `[PASSED]/[FAILED]` summary, no DataHub push:
```
[mother] kubectl -n weyland exec deploy/dagster-user-code -- /opt/soda-venv/bin/soda scan -d weyland -c /app/soda/configuration.yml /app/soda/checks/music.yml /app/soda/checks/health.yml
```

**Scan + push to DataHub Assertions** (exactly what `soda_scan_op` does — the `-srf` JSON is the venv↔main-env
bridge that `emit_soda_assertions` reads back):
```
[mother] kubectl -n weyland exec deploy/dagster-user-code -- bash -c '/opt/soda-venv/bin/soda scan -d weyland -c /app/soda/configuration.yml -srf /tmp/soda_results.json /app/soda/checks/music.yml /app/soda/checks/health.yml; echo ---EMIT---; python -c "import json,weyland_pipeline.datahub_emit as d; print(d.emit_soda_assertions(json.load(open(\"/tmp/soda_results.json\"))))"'
```

**Or run the whole thing through Dagster** (the scheduled path):
```
[mother] kubectl -n weyland exec deploy/dagster-user-code -- dagster job execute -j soda_quality_job -m weyland_pipeline.definitions
```

**Verify the assertion in DataHub GMS** (list assertions on a mart's trino URN):
```
[mother] kubectl -n data-mesh exec deploy/datahub-datahub-gms -- curl -s -H "Authorization: Bearer $(kubectl -n weyland get secret datahub-emit -o jsonpath='{.data.DATAHUB_GMS_TOKEN}' 2>/dev/null | base64 -d)" "http://localhost:8080/relationships?direction=OUTGOING&urn=urn%3Ali%3Adataset%3A%28urn%3Ali%3AdataPlatform%3Atrino%2Ciceberg.dbt.mart_country_health%2CPROD%29&types=Asserts" | head -c 400 ; echo
```
> `TODO: verify` the emit-token secret name (`datahub-emit`) with `kubectl -n weyland get secret | grep -i datahub`
> (carried over from [catalog-emit.md](catalog-emit.md)), and confirm the exact trino dataset URN casing for the
> mart. The always-available check is the DataHub UI Quality tab (above).

## Expected result

- The scan prints a `[PASSED]/[FAILED]` line per SodaCL check across the music + health marts; a healthy run is
  all `[PASSED]`.
- `emit_soda_assertions` upserts one stable `_NATIVE_` assertion per check (URN = `md5(table:check)`) plus an
  `AssertionRunEvent` (pass/fail) on each mart's `trino` URN — idempotent, so re-runs update the same assertions.
- Each mart's **Quality / Validations** tab in DataHub shows its checks with the latest verdict.
- An **emptiness tripwire** (`missing_percent(<col>) < 100`) fails loudly if a column is all-NULL — this is the
  class of bug dbt range checks pass vacuously (it caught the WHO GHO code-vs-label bug that nulled 7 columns in
  `mart_country_health`).

## Cleanup / teardown

The scan is **read-only against the marts** — it only issues aggregate SELECTs, creating no rows or tables. The
only artifacts are the DataHub assertions, which are **idempotent upserts** (a re-run re-asserts the same URNs);
normally leave them in place — they are the governance record.

To remove a throwaway assertion you emitted while testing, soft-delete it via the DataHub CLI in the GMS pod:
```
[mother] kubectl -n data-mesh exec deploy/datahub-datahub-gms -- datahub delete --urn "<assertion-urn>" --soft
```
> Whether the `datahub` CLI is on the GMS image is `TODO: verify`; if absent, use the DataHub UI (assertion →
> ⋯ → **Delete**), which is always available.
