# Soda — data-quality scan for the marts (L5, Slice C)

**What:** Soda Core runs an **independent** contract scan over the 7 dbt marts (`iceberg.dbt.mart_*`) — row
presence, key uniqueness/completeness, value-range bounds, and per-column **emptiness tripwires**. It's Slice C of
the L5 (Governance/Security) layer (Ranger + OPA + Soda). Complementary to dbt's in-transform tests: dbt validates
*during* the build (row-level, null-filtered); Soda validates the *published output* (aggregate) and so catches
all-NULL columns that dbt range checks pass vacuously.

**Where:**
- **No web UI** — Soda Cloud is paid ($0 rule). Results live in **two** places:
  - **Dagster** run logs (`soda_quality_job`) — the `[PASSED]/[FAILED]` breakdown.
  - **DataHub → each mart → Quality/Validations tab** — one `_NATIVE_` assertion per check (see `emit_soda_assertions`).
- Files (in the Dagster **user-code** image): `services/weyland-dagster/soda/configuration.yml` (Trino data source) ·
  `soda/checks/{music,health}.yml` (the checks). Op/job: `weyland_pipeline/definitions.py` (`soda_scan_op`,
  `soda_quality_job`, `soda_quality_schedule`). Emitter: `weyland_pipeline/datahub_emit.py` (`emit_soda_assertions`).
- Soda itself lives in an **isolated venv** `/opt/soda-venv` inside the user-code pod (its deps clash with
  dagster/dbt/datahub — the op shells out to it).

## Architecture / why it's built this way

- **Isolated venv.** `soda-core` pins opentelemetry/click/ruamel at versions incompatible with the main env, so it
  is installed into `/opt/soda-venv` (Dockerfile `python -m venv`) and invoked as a subprocess. `-srf <file>` writes
  a scan-results JSON that the main-env op reads back and feeds to `emit_soda_assertions` (the venv↔main-env bridge).
- **trino-noauth proxy.** Soda's Trino connector **always** sends HTTP Basic auth; Trino (no authenticator) rejects
  a password over plaintext (`401 Password not allowed for insecure authentication`). So `configuration.yml` points
  at `trino-noauth.data-mesh.svc.cluster.local:8080` (nginx strips the `Authorization` header → Trino sees
  `X-Trino-User: dbt`, the same no-auth path dbt/Superset use). **Do not** point it at `trino.data-mesh` directly.
  (dbt itself connects direct, method:none — the proxy is only for basic-auth connectors, cf. Lightdash.)
- **DataHub Assertions.** `emit_soda_assertions` mints a stable assertion URN `md5(table:check)` → a `_NATIVE_`
  DATASET assertion (the check text is the logic, no per-operator mapping) + an `AssertionRunEvent` (pass/fail) on
  the mart's `trino` URN. Idempotent; re-runs update the same assertion. Non-fatal — a DataHub hiccup never masks a
  data-quality failure.

## Run it

Scan only (prints the `[PASSED]/[FAILED]` summary):

```
kubectl -n weyland exec deploy/dagster-user-code -- /opt/soda-venv/bin/soda scan -d weyland -c /app/soda/configuration.yml /app/soda/checks/music.yml /app/soda/checks/health.yml
```

Scan **+** push results to DataHub Assertions (what `soda_scan_op` does):

```
kubectl -n weyland exec deploy/dagster-user-code -- bash -c '/opt/soda-venv/bin/soda scan -d weyland -c /app/soda/configuration.yml -srf /tmp/soda_results.json /app/soda/checks/music.yml /app/soda/checks/health.yml; echo ---EMIT---; python -c "import json,weyland_pipeline.datahub_emit as d; print(d.emit_soda_assertions(json.load(open(\"/tmp/soda_results.json\"))))"'
```

Or run the whole thing through Dagster: launch **`soda_quality_job`** in the UI. Nightly is `soda_quality_schedule`
(05:30, **STOPPED by default** — enable it once a manual run is green).

## Add / edit checks

Edit `soda/checks/{music,health}.yml` (SodaCL), then rebuild the user-code image (`bash ~/weyland-dagster/redeploy.sh`
on mother — the checks are COPY'd in). Emptiness tripwire pattern (catches an all-NULL column, which range checks
miss): `- missing_percent(<col>) < 100`.

## Gotchas

- **Node is tight** — `dagster-user-code` uses `strategy: Recreate` (RollingUpdate deadlocks: can't schedule the new
  pod beside the old on the ~98%-committed node). If a redeploy hangs on "old replicas pending termination", delete
  the old pod to free memory.
- **`iceberg.dbt.*` marts** are Trino-materialized — a model fix only takes effect after `dbt run` rebuilds the
  table: `kubectl -n weyland exec deploy/dagster-user-code -- sh -c 'cd /app/dbt && DBT_PROFILES_DIR=/app/dbt dbt run --select <model>'`.
- **WHO GHO code-vs-label** (fixed in `mart_country_health`): WHO stores `Dim1` as codes, not labels — pick each
  indicator's total (`SEX_BTSX` for sex-split, `ALCOHOLTYPE_SA_TOTAL` for alcohol, `null` for no-breakdown). The old
  `'both sexes'` label filter nulled 7 columns; Soda's emptiness tripwires caught them.
