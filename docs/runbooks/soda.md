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
- **Trino login (B233, 2026-10-23).** Soda's Trino connector sends HTTP Basic auth, and since B233 Trino takes it:
  `configuration.yml` points at `trino.data-mesh.svc.cluster.local:8443` (`http_scheme: https`,
  `auth_type: BasicAuthentication`, user `dbt`, `password: ${TRINO_PASSWORD}` resolved from the pod env). soda-core-trino
  has no CA option, so `soda_scan_op` runs the scan with `REQUESTS_CA_BUNDLE` set to the lab CA for that subprocess only
  ([trino.md § Authentication](trino.md#authentication-b233-2026-10-23)). Before B233 it went through the
  `trino-noauth` proxy with `NoAuthentication`, because Trino trusted `X-Trino-User`.
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

Edit `soda/checks/{music,health}.yml` (SodaCL), then rebuild the user-code image — the checks are COPY'd in.
**Use the registry flow, NOT `redeploy.sh`** (obsolete since B69 Wave 3; it builds a `:local` image nothing runs and
reports success anyway): `[rogueone] TAG=vN scripts/build-push-images.sh` → bump the tag in `k8s/dagster/user-code.yaml`
+ `k8s/dagster/dbt-docs.yaml` → push → Argo redeploys. Emptiness tripwire pattern (catches an all-NULL column, which range checks
miss): `- missing_percent(<col>) < 100`.

## Gotchas

- **Usage telemetry is off (owner, 2026-10-23).** Soda Core posted anonymous usage stats to `collect.soda.io` from the
  cluster unless its *user* config (`~/.soda/config.yml`, which it creates on first run with the stats on) says
  otherwise; the key is ignored in `configuration.yml`. `soda_scan_op` rewrites that file with
  `send_anonymous_usage_stats: false` before every scan (`weyland_pipeline/soda_telemetry.py`). Proven in the image: 3
  attempts to `collect.soda.io` with the default file, 0 with the opt-out.
- **`configuration.yml` is a Jinja template, comments included.** A literal dollar-brace placeholder in a comment fails
  every scan ("Error resolving Jinja template", 2026-10-23); placeholders belong only on the password lines.
- **Node is tight** — `dagster-user-code` uses `strategy: Recreate` (RollingUpdate deadlocks: can't schedule the new
  pod beside the old on the ~98%-committed node). If a redeploy hangs on "old replicas pending termination", delete
  the old pod to free memory.
- **`iceberg.dbt.*` marts** are Trino-materialized — a model fix only takes effect after `dbt run` rebuilds the
  table: `kubectl -n weyland exec deploy/dagster-user-code -- sh -c 'cd /app/dbt && DBT_PROFILES_DIR=/app/dbt dbt run --select <model>'`.
- **WHO GHO code-vs-label** (fixed in `mart_country_health`): WHO stores `Dim1` as codes, not labels — pick each
  indicator's total (`SEX_BTSX` for sex-split, `ALCOHOLTYPE_SA_TOTAL` for alcohol, `null` for no-breakdown). The old
  `'both sexes'` label filter nulled 7 columns; Soda's emptiness tripwires caught them.
