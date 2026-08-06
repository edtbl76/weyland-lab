# Demo — Great Expectations: auto-profile → validate → DataHub Assertions + Data Docs (B77 part b)

**What it shows:** the third data-quality source. Great Expectations auto-profiles the showcase tables, validates
them, surfaces every expectation as a DataHub Assertion **alongside Soda and the `@asset_check` gate**, and publishes
browsable Data Docs at `ge-docs.weyland.lab`. On-demand (a Dagster Job) so it costs ~$0 standing RAM.

## Run it

1. Dagster UI (`dagster.weyland.lab`) → **Jobs → `ge_validate_job` → Launch Run**. (Or wait — it's on-demand only, no schedule.)
2. Watch the op log. Expected, per table:
   ```
   iceberg.dbt.mart_country_health: 80 expectations profiled, checkpoint success=True
   iceberg.dbt.mart_spotify_audio: 106 expectations profiled, checkpoint success=False
   iceberg.datasets_music.spotify_tracks: 153 expectations profiled, checkpoint success=False
   ✓ Great Expectations → DataHub Assertions (B77 part b) → DataHub: 339
   ```
   The `checkpoint success=False` on two tables is **expected**: the `UserConfigurableProfiler` sets tight bounds
   (e.g. flags a sparse column all-null, caps `in_set` on high-cardinality columns), so a few expectations fail on
   the very data they were profiled from. The op is **advisory** — it exits 0, never failing the job; failing
   expectations just show red.

## Verify — one pane, three sources

- **DataHub** — open `iceberg.dbt.mart_country_health` → **Quality → Assertions**. GE's per-column expectations
  (`expect_column_values_to_not_be_null`, `expect_column_max_to_be_between`, …) sit next to the Soda checks and the
  `@asset_check` gate assertions — three independent DQ sources on one dataset.
- **Data Docs** — browse **`https://ge-docs.weyland.lab`** (Keycloak SSO). The **Validation Results** tab lists each
  table's run (green/red); **Expectation Suites** shows the auto-generated suites. This is nginx serving the
  `ge-data-docs` PVC that the run wrote (the run executes in the user-code pod via `DefaultRunLauncher`).

## How it's built (why these choices)

- **GE 0.18, isolated `/opt/ge-venv`** — GE's `sqlalchemy<2`/marshmallow pins clash with the dagster+dbt+datahub
  main env (same reason Soda runs isolated); and acryl-datahub 1.7 **dropped the native GE action**, so the
  GE→DataHub bridge is hand-rolled (`emit_ge_assertions` reads the validation-results JSON, like `emit_soda_assertions`).
- **Table asset + `UserConfigurableProfiler`** (not a query asset + the Onboarding Assistant) — a `SELECT * LIMIT`
  query asset profiled *table-level only* (2 expectations); a **table** asset lets GE introspect the schema so the
  profiler enumerates every column (80–153 expectations/table).
- **Trino via `trino-noauth`, user `dbt`** — the passwordless, Ranger-authorized path Soda already uses.

## Honest scope

GE here is a **showcase**, not the DQ-capability win. Its statistical/profiling edge is largely wasted on static
at-rest data (nothing drifts); the capability value came from **Soda-to-silver** ([soda-dq.md](soda-dq.md)). GE earns
its place as the auto-profiling + Data-Docs demonstration and a third assertion source. Flow:
[../diagrams/flow-great-expectations.md](../diagrams/flow-great-expectations.md).
