# Query cookbook — dbt marts (Trino / Iceberg)

The dbt transform tier (B1.5) materializes **7 tested marts** as Iceberg tables in the **`iceberg.dbt`** schema on
the Nessie `main` ref. Query them via Trino — IntelliJ (`jdbc:trino://trino.weyland.lab` or the svc `:8080`), the
Trino CLI, **Superset** (ad-hoc SQL — plain tables on the Trino connection), or **Lightdash** (dbt-native governed
metrics/explores — see [../runbooks/lightdash.md](../runbooks/lightdash.md)). The model DAG / lineage / test UI is
**dbt-docs.weyland.lab**. Built by `dagster-dbt` from the Iceberg gold; models in
`services/weyland-dagster/dbt/models/`, operate via [../runbooks/dbt.md](../runbooks/dbt.md), background in
`[[dbt-transform-tier]]`.

## The marts

| Mart | Grain | What |
|---|---|---|
| `mart_spotify_audio` | track | 11 audio features + genre, deduped, rare genres dropped (the classifier / Feast source) |
| `mart_genre_audio_profile` | genre | per-genre mean + stddev of the 11 features (audio "signature") |
| `mart_fma_genre_tree` | genre | FMA genre hierarchy (id / title / parent / top-level flag) |
| `mart_artist_popularity` | artist | Last.fm total plays + distinct listeners (approx) + MusicBrainz url |
| `mart_state_health_trends` | state × year | BRFSS chronic-condition prevalence (the Feast `state_health_risk` source) |
| `mart_country_health` | country × year | WHO GHO — 8 indicators pivoted |
| `mart_personality_by_country` | country | Big Five OCEAN trait means |
| `mart_macro_indicators` | series | FRED macro: latest value + prior-year value + `yoy_pct`, joined to the series dimension |
| `mart_company_financials` | company | SEC EDGAR: latest-annual revenue / net income / assets / liabilities / equity / EPS / shares per company, + SIC |

## Music

```sql
-- Loudest / most energetic genres (audio signature)
SELECT track_genre, round(energy_mean, 3) AS energy, round(danceability_mean, 3) AS dance, n_tracks
FROM iceberg.dbt.mart_genre_audio_profile
ORDER BY energy_mean DESC LIMIT 15;
```

```sql
-- Top artists by total plays
SELECT artist_name, total_plays, n_listeners, musicbrainz_url
FROM iceberg.dbt.mart_artist_popularity
ORDER BY total_plays DESC LIMIT 20;
```

```sql
-- FMA genre tree: each top-level genre and its number of sub-genres
SELECT p.genre_title AS top_genre, count(*) AS n_subgenres
FROM iceberg.dbt.mart_fma_genre_tree c
JOIN iceberg.dbt.mart_fma_genre_tree p ON c.parent_id = p.genre_id
WHERE p.is_top_level
GROUP BY p.genre_title ORDER BY n_subgenres DESC;
```

```sql
-- Feature profile of one genre
SELECT track_genre, count(*) AS n, round(avg(tempo), 1) AS avg_tempo, round(avg(valence), 3) AS avg_valence
FROM iceberg.dbt.mart_spotify_audio
WHERE track_genre = 'techno' GROUP BY track_genre;
```

## Health

```sql
-- Chronic-condition prevalence trend for a state
SELECT state, year, diabetes_pct, asthma_pct, copd_pct, depression_pct
FROM iceberg.dbt.mart_state_health_trends
WHERE state = 'CA' ORDER BY year;
```

```sql
-- States with the highest diabetes prevalence in the latest year
SELECT state, diabetes_pct
FROM iceberg.dbt.mart_state_health_trends
WHERE year = (SELECT max(year) FROM iceberg.dbt.mart_state_health_trends)
ORDER BY diabetes_pct DESC LIMIT 10;
```

```sql
-- Country health: life expectancy vs obesity / diabetes (latest first)
SELECT country, year, round(life_expectancy, 1) AS life_exp, round(adult_obesity, 1) AS obesity,
       round(diabetes_prevalence, 1) AS diabetes
FROM iceberg.dbt.mart_country_health
WHERE life_expectancy IS NOT NULL
ORDER BY year DESC, life_expectancy DESC LIMIT 15;
```

```sql
-- Most extraverted / open countries (Big Five, min 30 respondents by construction)
SELECT country, n_respondents, round(extraversion, 2) AS e, round(openness, 2) AS o
FROM iceberg.dbt.mart_personality_by_country
ORDER BY extraversion DESC LIMIT 10;
```

## Finance

`mart_macro_indicators` (B113 Phase 1) — one row per FRED macro series: latest observation + the value a year
earlier + `yoy_pct`, joined to the series dimension. YoY is "latest vs the most recent observation on or before
one year earlier", so it works across the mixed frequencies (daily DGS10, monthly UNRATE, quarterly GDPC1).

```sql
-- Latest value + year-over-year change per macro series
SELECT series_id, title, units, latest_date, latest_value, prior_year_value, yoy_pct
FROM iceberg.dbt.mart_macro_indicators
ORDER BY series_id;
```

```sql
-- Headline vs core inflation (CPI)
SELECT series_id, title, latest_value, yoy_pct
FROM iceberg.dbt.mart_macro_indicators
WHERE series_id IN ('CPIAUCSL', 'CPILFESL') ORDER BY series_id;
```

```sql
-- Indicators ranked by year-over-year change (biggest movers first)
SELECT series_id, title, round(yoy_pct, 2) AS yoy_pct
FROM iceberg.dbt.mart_macro_indicators
WHERE yoy_pct IS NOT NULL ORDER BY yoy_pct DESC;
```

`mart_company_financials` (Phase 2) — one row per company, latest-annual (10-K/FY) values pivoted to columns.

```sql
-- Mega-caps by revenue, with margin and the SIC industry
SELECT ticker, company, sic_description,
       revenue, net_income, round(net_income * 100.0 / nullif(revenue, 0), 1) AS net_margin_pct
FROM iceberg.dbt.mart_company_financials
ORDER BY revenue DESC LIMIT 15;
```

```sql
-- Balance-sheet leverage: assets vs liabilities vs equity
SELECT ticker, assets, liabilities, stockholders_equity,
       round(liabilities * 1.0 / nullif(stockholders_equity, 0), 2) AS debt_to_equity
FROM iceberg.dbt.mart_company_financials
WHERE stockholders_equity IS NOT NULL ORDER BY assets DESC LIMIT 15;
```

**`mart_price_daily`** (B113 Phase 4) — one row per ticker: the latest bar plus trailing-window analytics
(daily return, 30-day volatility daily + annualized, 52-week high/low, pct off the high).

```sql
-- Most volatile names and how far off their 52-week high they sit
SELECT ticker, latest_close, round(volatility_30d_annualized, 3) AS vol_ann,
       high_52w, low_52w, round(pct_off_52w_high, 3) AS off_high
FROM iceberg.dbt.mart_price_daily
ORDER BY vol_ann DESC LIMIT 20;
```

## Notes

- `iceberg.dbt` is the dbt output schema (Nessie `main`). Rebuild by materializing `weyland_dbt_assets` in Dagster
  (`dagster.weyland.lab`) or `dbt build` in the dagster pod — see `[[dbt-transform-tier]]`.
- Every mart is tested (dbt-utils `unique`/`unique_combination` + dbt-expectations ranges) — see each model's
  `schema.yml`.
- **Metrics layer:** the marts' `schema.yml` also carry **44 `meta.metrics`** (`avg_*`, `total_*_sum`, `*_count`)
  — Lightdash surfaces them as first-class governed metrics/explores over these same tables.
- Trino is a single node with a 4G heap; heavy ad-hoc queries can still pressure it. `mart_artist_popularity`
  uses `approx_distinct` for listeners so it doesn't OOM the aggregation.
