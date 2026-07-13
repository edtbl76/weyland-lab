# Query cookbook — Cube semantic layer + MetricFlow (B1.7 L6)

Two ways to query **governed metrics** over the dbt marts, instead of raw SQL:
- **Cube** — a headless semantic API (SQL / REST / GraphQL) over the 7 marts; define a measure once, query it anywhere.
- **MetricFlow** (dbt Semantic Layer) — metrics defined in the dbt project, queried with `mf query`.

Both compile to Trino under the hood. See [../runbooks/cube.md](../runbooks/cube.md), `[[cube-semantic-layer-b1.7]]`.

---

## Cube — SQL API (`:15432`, Postgres-wire)

Any pg client. **The one rule: wrap measures in `MEASURE()`** — dimensions select normally, but a measure column
(`avg_danceability`, `total_plays_sum`, …) selected as a bare column fails with *"could not be resolved from
available columns"*.

```
PGPASSWORD=weyland_dev_password psql -h cube.data-mesh.svc.cluster.local -p 15432 -U cube -d cube
```

```sql
-- most danceable genres
SELECT track_genre, MEASURE(avg_danceability) FROM spotify_audio GROUP BY 1 ORDER BY 2 DESC LIMIT 5;

-- life expectancy by country (governed metric)
SELECT country, MEASURE(avg_life_expectancy) FROM country_health GROUP BY 1 ORDER BY 2 DESC LIMIT 10;

-- top artists by plays
SELECT artist_name, MEASURE(total_plays_sum) FROM artist_popularity GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
```

### The 7 cubes (model in `k8s/cube/cube.yaml`)

| Cube | `sql_table` | Key measures | Dimensions |
|---|---|---|---|
| `spotify_audio` | `dbt.mart_spotify_audio` | `avg_danceability/energy/valence/tempo`, `count` | `track_genre`, `track_id` |
| `genre_audio_profile` | `dbt.mart_genre_audio_profile` | `avg_danceability_mean`, `total_tracks` | `track_genre` |
| `fma_genre_tree` | `dbt.mart_fma_genre_tree` | `count` | `genre_title`, `parent_title` |
| `artist_popularity` | `dbt.mart_artist_popularity` | `total_plays_sum`, `avg_listeners` | `artist_name` |
| `state_health_trends` | `dbt.mart_state_health_trends` | `avg_diabetes_pct`, `avg_depression_pct` | `state`, `year` |
| `country_health` | `dbt.mart_country_health` | `avg_life_expectancy/healthy_life_expectancy/diabetes_prevalence` | `country`, `year` |
| `personality_by_country` | `dbt.mart_personality_by_country` | `avg_openness/extraversion/conscientiousness`, `total_respondents` | `country` |

### From Superset

Add the DB `postgresql://cube:weyland_dev_password@cube.data-mesh.svc:15432/cube`, then build charts from a **SQL
Lab virtual dataset** using `MEASURE()` (Superset's auto-generated `AVG()` over a physical table is rejected by
Cube). The "Weyland — Cube Semantic Layer" dashboard + 5 datasets/charts are seeded by
`scripts/superset_seed_cube.py`.

### REST / GraphQL (`:4000`, for apps/agents)
```
POST https://cube.weyland.lab/cubejs-api/v1/load   (JWT signed with CUBEJS_API_SECRET)
{"query": {"measures": ["spotify_audio.avg_danceability"], "dimensions": ["spotify_audio.track_genre"]}}
```

---

## MetricFlow — `mf query` (in the dagster image)

Metrics defined in `services/weyland-dagster/dbt/models/semantic_models.yml`, spined by
`metricflow_time_spine.sql`. Scoped to the **time-shaped health marts** (`year` → a DATE axis; the categorical music
marts aren't a MetricFlow fit). Run inside the dagster user-code pod (`cd /app/dbt`, `DBT_PROFILES_DIR=/app/dbt`):

```
mf query --metrics life_expectancy --group-by metric_time__year --order metric_time__year
mf query --metrics state_diabetes_pct --group-by metric_time__year --order -metric_time__year --limit 10
mf query --metrics healthy_life_expectancy            # total (no group-by)
```

Metrics available: `life_expectancy`, `healthy_life_expectancy`, `diabetes_prevalence` (country) ·
`state_diabetes_pct`, `state_depression_pct` (US state). Add `--explain` to see the compiled Trino SQL.

**Gotchas:** MetricFlow needs a DAY-granularity time spine (Trino `sequence()` caps at 10k entries → the spine
cross-joins two small sequences for the 1960–2026 daily calendar); int `year` columns are cast to DATE in the
semantic model; empty tail years (no data) show blank — order descending to see the populated ones.
