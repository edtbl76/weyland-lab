# dbt — the transform tier (B1.5)

dbt Core (via **dbt-trino**) is the analytics-engineering layer **on top of** the Iceberg gold — it does NOT
re-ingest (datasets_lib owns land→silver→gold). It materializes **7 tested marts** as Iceberg tables in the
`iceberg.dbt` schema on the Nessie `main` ref: dbt compiles SQL to **Trino**, and **Trino writes the Iceberg
tables** (native-Nessie catalog supports writes). Project: `services/weyland-dagster/dbt/`, baked into the dagster
image. Marts + queries: [query/dbt-marts.md](../query/dbt-marts.md); background: `[[dbt-transform-tier]]`.

**Where the marts go from here (source of truth):** the cleaning/dedup/rare-genre filter lives ONCE in dbt, and
three consumers read the marts — **Feast** offline sources (`feast_setup`), the genre **trainer** (`--source mart`
via `mart_spotify_audio_export` → lakeFS, see [remote-training.md](remote-training.md)), and **DataHub** (below).
BI over the marts: **Lightdash** (governed dbt metrics, [lightdash.md](lightdash.md)) + Superset (ad-hoc SQL).

## Architecture

- **Adapter:** `dbt-trino`, `profiles.yml` = `method: none, host: trino.data-mesh.svc:8080, http_scheme: http,
  database: iceberg (catalog), schema: dbt, threads: 2`. Trino is no-auth on the LAN.
- **Models:** staging = **ephemeral** (inlined, no table); marts = **table** (real Iceberg tables). Sources = the
  gold tables (`iceberg.datasets_music/health.*`).
- **Manifest baked at image BUILD:** the Dockerfile runs `dbt deps && dbt parse` → `dbt/target/manifest.json`;
  `@dbt_assets` reads it at import time. A build-time parse failure breaks the whole dagster image.
- **Orchestration:** `dagster-dbt` — `weyland_dbt_assets` in `weyland_pipeline/dbt_assets.py`.

## Build / run

- **Scheduled:** `weyland_dbt_job` / `weyland_dbt_schedule` (in `weyland_pipeline/schedules/__init__.py`) — weekly
  **Sunday 06:00 NY**. The gold is near-static, so weekly re-materialize + re-test is enough.
- **On demand:** materialize `weyland_dbt_assets` in the Dagster UI (`dagster.weyland.lab`), or in the pod:
  `kubectl -n weyland exec deploy/dagster-user-code -- sh -c "cd /app/dbt && DBT_PROFILES_DIR=/app/dbt dbt build"`
  (in-cluster/meshed → reaches Trino, no port-forward).
- **Code change → rebuild the image (B69 Wave 3 flow — `redeploy.sh` is OBSOLETE and now refuses to run):** the
  user-code image lives at `registry.weyland.lab/weyland-dagster-user-code:<TAG>` with `IfNotPresent`, so only a
  **NEW TAG** makes nodes re-pull. (1) `[rogueone] TAG=vN scripts/build-push-images.sh`, (2) bump the tag in BOTH
  `k8s/dagster/user-code.yaml` and `k8s/dagster/dbt-docs.yaml`, (3) push → Argo redeploys. Images to the registry
  FIRST, manifests second, or Argo lands in ImagePullBackOff. Building `:local` + `ctr import` appears to succeed
  and changes NOTHING.

## The marts (7, all tested)

Music: `mart_spotify_audio`, `mart_genre_audio_profile`, `mart_fma_genre_tree`, `mart_artist_popularity`.
Health: `mart_state_health_trends`, `mart_country_health`, `mart_personality_by_country`. Each has dbt-utils +
dbt-expectations tests AND (2026-07-08) a **metrics layer**: 44 `meta.metrics` in the marts' `schema.yml`
(`avg_*`, `total_*_sum`, `*_count`, …) that Lightdash surfaces as first-class metrics. **Rule:** a metric name
must never equal a column/dimension name (a `total_plays` metric on the `total_plays` column errored → renamed
`total_plays_sum`).

## dbt-docs UI

`dbt-docs.weyland.lab` (forward-auth) = the model DAG / lineage / test-coverage UI (dbt Core's built-in). Reuses
the dagster image, meshed → Trino. `k8s/dagster/dbt-docs.yaml`. **Refresh = `kubectl -n weyland rollout restart
deploy/dbt-docs`** (regenerates `dbt docs generate` against the current marts).

## DataHub cataloging — TWO ways

1. **Custom `emit_dbt`** (`datahub_emit.py`, run by `datahub_catalog_emit_job`) — walks the baked manifest offline
   → the 7 marts as Trino/Iceberg datasets `iceberg.dbt.mart_*` + a `dbt` tag + gold→mart lineage. No Trino needed.
   `emit_feast` adds the mart→Feast-source lineage edge.
2. **Native dbt connector** — `k8s/data-mesh/datahub-ingestion/dbt.recipe.yaml` (UI-pasted managed ingestion),
   `target_platform: trino` so the dbt models **sibling** onto the same `iceberg.dbt.*` URNs, adding
   tests-as-assertions + column lineage. It reads `manifest.json`+`catalog.json` from **`s3://warehouse/_dbt_artifacts/`**.

### Artifact publish (for the connector)

`catalog.json` can't come from the dbt-docs pod (its boot-time `dbt docs generate` races Trino → missing catalog
→ connector `JSONDecodeError`). Instead the **`weyland_dbt_assets` run publishes it**: after `build`,
`publish_dbt_artifacts()` runs `dbt docs generate` against live Trino and uploads `manifest.json`+`catalog.json`
to `s3://warehouse/_dbt_artifacts/` (NOT `warehouse/dbt/` — that's the Iceberg `dbt` schema's data). Bootstrap /
refresh without a full rebuild:

```
kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/publish_dbt_artifacts.py
```

The connector recipe reads s3 with path-style + the `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` DataHub Secrets (nessie
S3 creds). If those Secrets are unset it fails `NoCredentialsError`. Manifest-only HTTP fallback (drop
`catalog_path` + `aws_connection`, point `manifest_path` at the dbt-docs svc) loses catalog stats but keeps
models/tests/lineage.

## Troubleshooting

- **Trino OOM crashloop (the big one).** Heavy aggregations exhaust Trino's heap; with `-XX:+ExitOnOutOfMemoryError`
  the JVM exits → pod restarts → every dbt query 503s while the Service/AGE still read "up" (only RESTARTS climb).
  Fix already applied: `approx_distinct` (not `count(distinct)`) for high-cardinality, `threads: 2`, and Trino
  `-Xmx4G` / pod limit 6Gi (`k8s/data-mesh/trino.yaml`). See `[[dbt-transform-tier]]`.
- **Iceberg 15M-row writer cap** (`ICEBERG_MAX_ROWS`) → `usda …food_nutrient` (26.8M) isn't in Iceberg, so a
  `mart_food_nutrition` is blocked (only ClickHouse has that table). Deferred.
- **DataHub dbt connector 503/JSONDecodeError/NoCredentials** → the artifact-publish + MinIO-Secret gotchas above.

See also: [query/dbt-marts.md](../query/dbt-marts.md), [lightdash.md](lightdash.md), [trino.md](trino.md),
[remote-training.md](remote-training.md), `[[dbt-transform-tier]]`.
