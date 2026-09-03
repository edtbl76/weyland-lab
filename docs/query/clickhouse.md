# ClickHouse — query cookbook

**Connect:** `/play` UI at `clickhouse.weyland.lab/play` (Keycloak-gated), or IntelliJ/DataGrip at
`127.0.0.1:8123` (port-forward the `clickhouse` svc; user `default`, blank password; if the driver throws
`[08000] databaseTerm/session_id`, **add** `databaseTerm=schema` in Advanced). In-pod:
`kubectl -n data-mesh exec deploy/clickhouse -- clickhouse-client -q "…"`.

Databases: `datasets_music`, `datasets_health`. Tables are per silver parquet file, MergeTree, `ORDER BY tuple()`.

### Explore
```sql
-- every loaded table + row count
SELECT database, name, total_rows, formatReadableSize(total_bytes) AS size
FROM system.tables WHERE database LIKE 'datasets_%' ORDER BY total_rows DESC;

-- columns of a table
SELECT name, type FROM system.columns
WHERE database='datasets_health' AND table='usda_fooddata_fooddata_central_csv_2024_10_31_food';
```

### USDA FoodData Central (`datasets_health`)
The relational USDA set — `food` (2M), `food_nutrient` (26.8M), `nutrient`, `branded_food`, `food_category`.
```sql
-- how many nutrient measurements per food, top 20 most-measured foods
SELECT f.description, count() AS nutrients
FROM datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_food AS f
JOIN datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_food_nutrient AS fn ON fn.fdc_id = f.fdc_id
GROUP BY f.description ORDER BY nutrients DESC LIMIT 20;

-- nutrient catalog by unit
SELECT unit_name, count() AS n FROM datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_nutrient
GROUP BY unit_name ORDER BY n DESC;

-- branded foods by brand owner
SELECT brand_owner, count() AS products
FROM datasets_health.usda_fooddata_fooddata_central_csv_2024_10_31_branded_food
GROUP BY brand_owner ORDER BY products DESC LIMIT 25;
```

### Open Food Facts (`datasets_health.open_food_facts`)
Wide (211 cols), ~4.5M products.
```sql
SELECT countries_en, count() AS n FROM datasets_health.open_food_facts
GROUP BY countries_en ORDER BY n DESC LIMIT 20;

-- nutrition-grade distribution
SELECT nutrition_grade_fr AS grade, count() AS n FROM datasets_health.open_food_facts
WHERE grade != '' GROUP BY grade ORDER BY grade;

-- highest-sugar products with a name
SELECT product_name, sugars_100g FROM datasets_health.open_food_facts
WHERE product_name != '' AND sugars_100g IS NOT NULL ORDER BY sugars_100g DESC LIMIT 20;
```

### Music (`datasets_music`)
```sql
-- FMA: genre distribution (fma_tracks)
SELECT track_genre_top AS genre, count() AS n FROM datasets_music.fma_tracks
WHERE genre != '' GROUP BY genre ORDER BY n DESC LIMIT 20;

-- UCI YearPrediction: songs per release year (515k)
SELECT year, count() AS n FROM datasets_music.uci_year_prediction GROUP BY year ORDER BY year;

-- AudioSet: label frequency
SELECT label, count() AS n FROM datasets_music.audioset_train GROUP BY label ORDER BY n DESC LIMIT 25;

-- MusicBrainz (HF subset — NOT the full mirror; that's in Postgres): artists by area
SELECT area, count() AS n FROM datasets_music.musicbrainz_musicbrainz_artist
GROUP BY area ORDER BY n DESC LIMIT 20;

-- LP-MusicCaps: caption length distribution
SELECT length(caption) AS len, count() AS n FROM datasets_music.lp_musiccaps_mc_train
GROUP BY len ORDER BY len;
```

### Finance (`datasets_finance`)

FRED macro (B113 Phase 1) — `fred_macro` (long: `series_id`, `date`, `value`) + `fred_series_meta` — ingested via
the native `s3()` path. This is the source the Superset **"Weyland Finance — Macro Time Series"** line charts read
(ClickHouse, not the Timescale hypertable). `value` is NULL for FRED's `"."` gaps.

```sql
SELECT name FROM system.tables WHERE database = 'datasets_finance';

-- span + coverage per series
SELECT series_id, min(date) AS first_obs, max(date) AS last_obs, count() AS n
FROM datasets_finance.fred_macro
GROUP BY series_id ORDER BY series_id;

-- rates over time (the line-chart shape): monthly average per series
SELECT toStartOfMonth(date) AS month, series_id, avg(value) AS v
FROM datasets_finance.fred_macro
WHERE series_id IN ('FEDFUNDS','DGS2','DGS10') AND value IS NOT NULL
GROUP BY month, series_id ORDER BY month DESC LIMIT 30;
```

### ClickHouse-isms worth knowing
- `ORDER BY tuple()` = no sorting key (we dump; fine for a lab). Add a real `ORDER BY` if you want fast filters.
- `SELECT * FROM s3(url, key, secret, 'Parquet')` reads parquet straight from lakeFS — that's how the loader ingests.
- `formatReadableSize()`, `topK(n)(col)`, `quantile(0.95)(col)` are handy for quick profiling.
