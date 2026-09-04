# GizmoSQL — query cookbook

**Connect:** GizmoSQL is **DuckDB served over Arrow Flight SQL** — a real `host:port` in front of an
otherwise embedded-only engine. Two client paths:

- **IntelliJ / DataGrip:** add the **Arrow Flight SQL JDBC** driver (Maven
  `org.apache.arrow:flight-sql-jdbc-driver:17.0.0`, class `org.apache.arrow.driver.jdbc.ArrowFlightJdbcDriver`),
  then a data source with URL (creds are **URL params** — the driver has no separate cred fields; use the
  shared dev password from the `gizmosql-secret` k8s Secret, not the literal):
  ```
  jdbc:arrow-flight-sql://mother:31337?useEncryption=false&user=weyland&password=<gizmosql-secret GIZMOSQL_PASSWORD>
  ```
  No SSH tunnel/SSL — the NodePort is LAN-reachable and the app runs plaintext (`grpc+tcp://`, TLS ingress = B69).
- **ADBC (pipelines, in-pod):** the Dagster catalog emitter connects `grpc+tcp://gizmosql.data-mesh.svc:31337`
  (in-cluster Istio mTLS covers the hop). In-pod ad-hoc uses the same ADBC Flight SQL driver.

Schemas: `datasets_music`, `datasets_health` — the silver materialised as **persisted DuckDB base tables** (one
per lakeFS Parquet file) on a PVC. See [runbook](../runbooks/gizmosql.md) for materialise/refresh.

### Explore
```sql
-- every loaded table (Flight SQL GetTables surfaces base tables; the IDE tree builds from this)
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_schema LIKE 'datasets_%' ORDER BY table_schema, table_name;

-- columns of a table
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'datasets_health' AND table_name = 'who_gho_life_expectancy';

-- row count
SELECT count(*) FROM datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_food;
```

### USDA FoodData Central (`datasets_health.usda_fooddata_..._<table>`)
The relational USDA set — `food`, `food_nutrient`, `nutrient`, `branded_food`, `food_category`, plus ~30 more.
DuckDB does real JOINs (unlike the Cassandra/wide-column cells).
```sql
-- most-measured foods (top 20 by nutrient-measurement count)
SELECT f.description, count(*) AS nutrients
FROM datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_food f
JOIN datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_food_nutrient fn USING (fdc_id)
GROUP BY f.description ORDER BY nutrients DESC LIMIT 20;

-- nutrient catalog by unit
SELECT unit_name, count(*) AS n
FROM datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_nutrient
GROUP BY unit_name ORDER BY n DESC;

-- branded foods by brand owner
SELECT brand_owner, count(*) AS products
FROM datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_branded_food
GROUP BY brand_owner ORDER BY products DESC LIMIT 25;
```

### Open Food Facts (`datasets_health.open_food_facts`)
Wide product table.
```sql
SELECT countries_en, count(*) AS n FROM datasets_health.open_food_facts
GROUP BY countries_en ORDER BY n DESC LIMIT 20;

-- nutrition-grade distribution
SELECT nutrition_grade_fr AS grade, count(*) AS n FROM datasets_health.open_food_facts
WHERE grade IS NOT NULL AND grade != '' GROUP BY grade ORDER BY grade;
```

### WHO GHO (`datasets_health.who_gho_*`)
8 tables — `who_gho_life_expectancy`, `_adult_obesity`, `_alcohol_consumption`, `_diabetes_prevalence`,
`_hypertension`, `_tobacco_smoking`, `_healthy_life_expectancy`, `_mental_health_disorders`.
```sql
-- life expectancy trend for one country (no partition-key constraint here — it's DuckDB, scan freely)
SELECT timedim, numericvalue FROM datasets_health.who_gho_life_expectancy
WHERE spatialdim = 'USA' ORDER BY timedim;

-- obesity: latest value per country, top 20
SELECT spatialdim, max_by(numericvalue, timedim) AS latest_obesity
FROM datasets_health.who_gho_adult_obesity GROUP BY spatialdim
ORDER BY latest_obesity DESC LIMIT 20;
```

### BRFSS / NHANES / NHIS / big_five (`datasets_health`)
```sql
-- BRFSS chronic-condition prevalence rows
SELECT count(*) FROM datasets_health.brfss_brfss_prevalence_2011_present;

-- NHANES body measures (2017-2020 wave)
SELECT * FROM datasets_health.nhanes_2017_2020_bmx_j LIMIT 20;

-- OCEAN personality inventory by country
SELECT country, count(*) AS n FROM datasets_health.big_five_big5_data
GROUP BY country ORDER BY n DESC LIMIT 25;
```

### Music (`datasets_music`)
```sql
-- FMA: top genres (fma_tracks — the clean canonical table, not the hash-suffixed run artifacts)
SELECT track_genre_top AS genre, count(*) AS n FROM datasets_music.fma_tracks
WHERE genre IS NOT NULL AND genre != '' GROUP BY genre ORDER BY n DESC LIMIT 20;

-- UCI YearPrediction: songs per release year
SELECT year, count(*) AS n FROM datasets_music.uci_year_prediction GROUP BY year ORDER BY year;

-- MusicBrainz (HF subset — NOT the full mirror; that lives in Tier-2 Postgres): artists by area
SELECT area, count(*) AS n FROM datasets_music.musicbrainz_musicbrainz_artist
GROUP BY area ORDER BY n DESC LIMIT 20;

-- Last.fm: heaviest listeners (lifetime play counts, no timestamps)
SELECT user_id, sum(play_count) AS total_plays FROM datasets_music.lastfm
GROUP BY user_id ORDER BY total_plays DESC LIMIT 20;

-- LP-MusicCaps: caption length distribution
SELECT length(caption) AS len, count(*) AS n FROM datasets_music.lp_musiccaps_mc_train
GROUP BY len ORDER BY len;

-- Spotify audio features (spotify_tracks — clean table)
SELECT round(avg(danceability), 3) AS danceability, round(avg(energy), 3) AS energy
FROM datasets_music.spotify_tracks;
```

### Finance (`datasets_finance`)

FRED macro (B113 Phase 1) as persisted DuckDB base tables — `fred_macro` (long: `series_id`, `date`, `value`) +
`fred_series_meta`. `value` is NULL for FRED's `"."` gaps.

```sql
-- the finance tables (GetTables surfaces base tables)
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_schema = 'datasets_finance' ORDER BY table_name;

-- observations per series (DuckDB aggregates locally)
SELECT series_id, count(*) AS n_obs, count(value) AS n_present
FROM datasets_finance.fred_macro
GROUP BY series_id ORDER BY n_obs DESC;
```

Phase 2 adds the SEC EDGAR tables — `company_financials` (long facts), `company_meta` (dim), `company_filings`
(10-K/10-Q history).

```sql
-- latest annual revenue per company (DuckDB window over the long facts)
SELECT ticker, company, period_end, value AS revenue FROM (
  SELECT ticker, company, period_end, value,
         row_number() OVER (PARTITION BY cik ORDER BY period_end DESC) AS rn
  FROM datasets_finance.company_financials
  WHERE concept = 'revenue' AND form = '10-K' AND fp = 'FY' AND value IS NOT NULL
) WHERE rn = 1 ORDER BY revenue DESC;
```

## Notes — GizmoSQL / DuckDB-isms

- **DataGrip can't browse non-default schemas in its tree.** The JDBC client only surfaces the *default*
  schema; `datasets_music` / `datasets_health` show but expand to nothing in some driver versions (the
  server-side metadata via ADBC is fine — it's a client limitation). Workaround: run queries against the
  fully-qualified name, or open **`sql/gizmosql_browse.sql`** (a generated `SELECT * … LIMIT 100` per table —
  put the cursor on a line and execute it to see columns). Regenerate it after dataset changes with
  `gen_gizmosql_init.py queries > sql/gizmosql_browse.sql`.
- **Base tables, not views.** GizmoSQL's Flight SQL `GetTables` surfaces base tables but **not** views — DuckDB
  views were queryable-by-name yet invisible in the IDE tree. The silver is materialised as `CREATE TABLE` so
  it's browsable *and* hits native columnar storage (no Parquet re-read per query).
- **Hash-suffixed tables** (e.g. `fma_tracks_1782666876_...`) are historical multi-run artifacts — **prefer the
  clean canonical name** (`fma_tracks`, `fma_echonest`, `spotify_tracks`, `fma_genres`). One deterministic
  Parquet file per table is the current shape.
- **Real DuckDB SQL** — full JOINs, `USING`, `max_by()`/`arg_max()`, `quantile_cont()`, `list_aggr()`,
  `SUMMARIZE <table>` for instant column profiling, `read_parquet('s3://…')` to reach lakeFS directly.
- GizmoSQL is the **single-node OLAP** half of the query layer; **Trino** is the distributed-federation half —
  see [arch.md §7a](../arch.md) for the when-to-use-which matrix. For the deploy/refresh mechanics and gotchas
  (`enableServiceLinks: false`, `strategy: Recreate`, S3 `REGION`, plaintext TLS), read the
  [GizmoSQL runbook](../runbooks/gizmosql.md).

Related: [[k8s-rwo-recreate-strategy]] · [[gizmosql-datagrip-tree-browse-limitation]] ·
[Cassandra cookbook](cassandra.md) · [ClickHouse cookbook](clickhouse.md)
