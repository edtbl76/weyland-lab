# Query cookbook — Trino / Iceberg (the general entry point)

Trino is the lab's **federation query engine** — one SQL surface over the Nessie **Iceberg lake** (`iceberg`
catalog) and the **`weyland` Postgres** (`postgresql` catalog). This cookbook covers the **gold Iceberg tables**
(the `datasets_music` / `datasets_health` schemas), catalog federation, and cross-catalog joins. For the curated
dbt marts (`iceberg.dbt.*`) see **[[dbt-marts]]** — don't duplicate them here. Background: `[[trino]]` runbook,
`[[datasets-lake]]`, `[[trino-nessie-native-catalog]]`.

## Connect

- **CLI (in-pod):** `kubectl -n data-mesh exec -it deploy/trino -- trino` → `trino>` prompt. No auth.
- **IntelliJ / DataGrip:** forward port **8080** on the `trino` svc via the IntelliJ Kubernetes plugin
  (Services → trino → Forward Ports), then a **Trino** data source at `jdbc:trino://localhost:8080`, user any /
  no password. In-cluster the svc is `trino.data-mesh.svc:8080`.
- **Web UI:** `https://trino.weyland.lab` (forward-auth → Keycloak, then Trino username-only login) — this is a
  **monitoring console** (running queries, timings, cluster), NOT a query editor. Run SQL via CLI / IntelliJ /
  **Superset** (Trino is a Superset database).

## Catalogs & what's queryable

| Catalog | Schema | What |
|---|---|---|
| `iceberg` | `datasets_music` | **gold** music Iceberg tables — one per raw file (`<folder>` or `<folder>_<file>`) |
| `iceberg` | `datasets_health` | **gold** health Iceberg tables — same naming |
| `iceberg` | `dbt` | 7 curated dbt marts — **see [[dbt-marts]]** |
| `iceberg` | `catalog`, `eval` | RAG / eval lake tables |
| `postgresql` | `public`, … | the `weyland` app DB over JDBC (federation target) |
| `system` | — | Trino internals (`system.metadata`, `system.runtime`) |

Gold tables are hydrated by the Dagster transform broker (`[[datasets-lake]]`) into the flat Nessie namespaces
`datasets_music` / `datasets_health` (Nessie **nested** namespaces are invisible to Trino's native Nessie catalog,
so everything is one level deep). Table id = the raw folder, or `<folder>_<file>` for multi-file folders.

### Discover — always start here (names are per-file)

```sql
SHOW CATALOGS;                              -- iceberg, postgresql, system
SHOW SCHEMAS FROM iceberg;                  -- datasets_music, datasets_health, dbt, catalog, eval
SHOW TABLES FROM iceberg.datasets_music;    -- the real gold table names
SHOW TABLES FROM iceberg.datasets_health;
DESCRIBE iceberg.datasets_music.spotify_tracks;   -- columns + types
```

## Music gold (`iceberg.datasets_music`)

Verified table ids: `spotify_tracks`, `fma_tracks`, `fma_features`, `uci_year_prediction` (single-file folders →
just the folder name). Multi-file folders (audioset, lp_musiccaps, musicbrainz splits) expand to
`<folder>_<file>` — run `SHOW TABLES` for the exact ids.

```sql
-- Spotify: genre distribution (the classifier / Feast source, before dbt dedups it)
SELECT track_genre, count(*) AS n
FROM iceberg.datasets_music.spotify_tracks
GROUP BY track_genre ORDER BY n DESC LIMIT 20;
```

```sql
-- Spotify: audio-feature profile of one genre
SELECT track_genre, count(*) AS n,
       round(avg(tempo), 1)   AS avg_tempo,
       round(avg(energy), 3)  AS avg_energy,
       round(avg(valence), 3) AS avg_valence
FROM iceberg.datasets_music.spotify_tracks
WHERE track_genre = 'techno'
GROUP BY track_genre;
```

```sql
-- UCI YearPrediction (MSD subset, ~515k): songs per release year
SELECT year, count(*) AS n
FROM iceberg.datasets_music.uci_year_prediction
GROUP BY year ORDER BY year;
```

## Health gold (`iceberg.datasets_health`)

Verified id: `brfss_brfss_prevalence_2011_present` (folder `brfss` + file `brfss_prevalence_2011_present`). WHO GHO
lands one JSON per indicator → `who_gho_<indicator>` (multiple tables — `SHOW TABLES` for the set).

```sql
-- BRFSS chronic-condition prevalence — columns first, then a slice
DESCRIBE iceberg.datasets_health.brfss_brfss_prevalence_2011_present;

SELECT *
FROM iceberg.datasets_health.brfss_brfss_prevalence_2011_present
LIMIT 25;
```

```sql
-- WHO GHO indicators (one table per indicator; discover names with SHOW TABLES FROM iceberg.datasets_health)
SELECT * FROM iceberg.datasets_health.who_gho_who_life_expectancy_at_birth_years LIMIT 25;
```

## Finance gold (`iceberg.datasets_finance`)

FRED macro (B113 Phase 1) — `fred_macro` (tidy/long: `series_id`, `date`, `value`; one row per series×date) +
`fred_series_meta` (the dimension). ~13 series at mixed frequencies (daily DGS10, monthly UNRATE, quarterly GDPC1).
`value` is NULL where FRED reported `"."` — always `WHERE value IS NOT NULL` for aggregates. The curated
latest-value + YoY view is the `mart_macro_indicators` mart ([dbt-marts.md](dbt-marts.md)).

```sql
SHOW TABLES FROM iceberg.datasets_finance;            -- fred_macro, fred_series_meta
DESCRIBE iceberg.datasets_finance.fred_macro;

-- latest non-null observation per series, labelled from the dimension
WITH latest AS (
  SELECT series_id, max(date) AS latest_date
  FROM iceberg.datasets_finance.fred_macro WHERE value IS NOT NULL GROUP BY series_id
)
SELECT m.series_id, meta.title, meta.units, f.date AS latest_date, f.value AS latest_value
FROM latest m
JOIN iceberg.datasets_finance.fred_macro f ON f.series_id = m.series_id AND f.date = m.latest_date
LEFT JOIN iceberg.datasets_finance.fred_series_meta meta ON meta.series_id = m.series_id
ORDER BY m.series_id;

-- CPI year-over-year from the raw monthly index (LAG 12)
WITH cpi AS (
  SELECT date, value, lag(value, 12) OVER (ORDER BY date) AS value_year_ago
  FROM iceberg.datasets_finance.fred_macro WHERE series_id = 'CPIAUCSL' AND value IS NOT NULL
)
SELECT date, value, round((value - value_year_ago) / value_year_ago * 100.0, 2) AS yoy_pct
FROM cpi WHERE value_year_ago IS NOT NULL ORDER BY date DESC LIMIT 24;

-- yield-curve spread (10y − 2y Treasury); negative = the classic inversion signal
SELECT t10.date, t10.value AS dgs10, t2.value AS dgs2, round(t10.value - t2.value, 2) AS spread_10y_2y
FROM iceberg.datasets_finance.fred_macro t10
JOIN iceberg.datasets_finance.fred_macro t2 ON t2.date = t10.date AND t2.series_id = 'DGS2'
WHERE t10.series_id = 'DGS10' AND t10.value IS NOT NULL AND t2.value IS NOT NULL
ORDER BY t10.date DESC LIMIT 30;
```

## Cross-catalog federation (`iceberg` + `postgresql`)

Trino's whole point: join the lake to the live app DB in one query — no ETL. The `postgresql` catalog is the
`weyland` Postgres over JDBC (it works through the STRICT mesh because Istio passes TCP through). Discover, then
join fully-qualified `catalog.schema.table` on both sides.

```sql
-- what's in the app DB
SHOW SCHEMAS FROM postgresql;
SHOW TABLES FROM postgresql.public;
```

```sql
-- Federated join skeleton: gold Iceberg (left) ⋈ a weyland Postgres table (right).
-- Fully-qualify BOTH sides with catalog.schema.table — no shared connection needed.
SELECT i.track_genre, count(*) AS n
FROM iceberg.datasets_music.spotify_tracks AS i
JOIN postgresql.public.<some_table> AS p
  ON p.genre = i.track_genre
GROUP BY i.track_genre
ORDER BY n DESC;
```

You can also federate **across schemas in the same catalog** — e.g. join a gold table to a dbt mart
(`iceberg.datasets_music.spotify_tracks` ⋈ `iceberg.dbt.mart_genre_audio_profile`) since both live in the
`iceberg` catalog. See **[[dbt-marts]]** for the mart columns.

## Iceberg time-travel & snapshots

Gold tables are real Iceberg tables on the Nessie `main` ref, so the Iceberg connector's metadata tables and
time-travel syntax work.

```sql
-- Snapshot history of a table (id, timestamp, operation, manifest)
SELECT snapshot_id, committed_at, operation
FROM iceberg.datasets_music."spotify_tracks$snapshots"
ORDER BY committed_at DESC;

-- Other Iceberg metadata tables: $history, $files, $partitions, $manifests
SELECT * FROM iceberg.datasets_music."spotify_tracks$files" LIMIT 10;
```

```sql
-- Read the table AS OF a past snapshot (rollback-safe inspection)
SELECT count(*) FROM iceberg.datasets_music.spotify_tracks
FOR VERSION AS OF <snapshot_id>;

-- ...or as of a wall-clock time
SELECT count(*) FROM iceberg.datasets_music.spotify_tracks
FOR TIMESTAMP AS OF TIMESTAMP '2026-07-01 00:00:00 UTC';
```

Note: the transform broker `overwrite()`s each table per run, so each materialization is a fresh snapshot — time-travel
lets you diff runs. Versioning is also tracked in Nessie (`nessie.weyland.lab`) at the branch level.

## Notes

- **Single node, 4G heap — mind the aggregations.** Heavy ad-hoc GROUP BYs / DISTINCTs can OOM-crashloop Trino
  (looks like "Trino down", only the pod RESTARTS climb). Prefer `approx_distinct(col)` over `count(distinct col)`,
  filter early, and `LIMIT` while exploring. This is the same guard the dbt marts use (`[[dbt-marts]]`, `[[dbt-transform-tier]]`).
- **Not every table reaches gold Iceberg.** The broker defers tables over **15M rows** from Iceberg
  (`ICEBERG_MAX_ROWS`) — e.g. USDA `food_nutrient` (~24M), `open_food_facts` (~9GB). Those are absent from
  `datasets_*` gold but present in the silver file formats and in **ClickHouse** — see **[[clickhouse]]**.
- **Native Nessie catalog** (`iceberg.catalog.type=nessie`, API v2), not generic `type=rest` — see
  `[[trino-nessie-native-catalog]]`. Schemas are flat (`datasets_music`, not nested).
- **No catalog auto-reload** — after a Trino configmap change, `kubectl -n data-mesh rollout restart deploy/trino`.
- **Quote `$` metadata tables** — `"table$snapshots"` needs the double-quotes.
