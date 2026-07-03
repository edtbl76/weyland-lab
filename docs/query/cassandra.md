# Cassandra — query cookbook

**Connect:** IntelliJ/DataGrip → Apache Cassandra driver, port-forward the `cassandra` svc `9042` (user/pass
blank — no auth). In-pod: `kubectl -n data-mesh exec -it cassandra-0 -- cqlsh`.

Keyspaces: `datasets_music`, `datasets_health`. Every table has a synthetic `row_id uuid` clustering column and
a natural **partition key** — so **filter by the partition key** or you'll do a (slow, warned) full scan.

### Explore
```sql
DESCRIBE KEYSPACES;
USE datasets_health;
DESCRIBE TABLES;
DESCRIBE TABLE who_gho_life_expectancy;   -- see the PRIMARY KEY ((partition), row_id)
```

### WHO GHO (`datasets_health`, partition = `spatialdim` = country)
8 tables: `who_gho_life_expectancy`, `_adult_obesity`, `_alcohol_consumption`, `_diabetes_prevalence`,
`_hypertension`, `_tobacco_smoking`, `_healthy_life_expectancy`, `_mental_health_disorders`.
```sql
-- all life-expectancy rows for one country (partition query — the fast path)
SELECT timedim, numericvalue FROM datasets_health.who_gho_life_expectancy
WHERE spatialdim = 'USA';

-- obesity for a country, most recent years first
SELECT timedim, numericvalue FROM datasets_health.who_gho_adult_obesity
WHERE spatialdim = 'GBR' ORDER BY row_id;   -- clustering is row_id; add ALLOW FILTERING for other filters
```

### big_five (`datasets_health`, partition = `country`)
OCEAN personality inventory responses.
```sql
SELECT * FROM datasets_health.big_five_big5_data WHERE country = 'US' LIMIT 50;
-- note: blank/NULL countries were bucketed to '__UNKNOWN__' (Cassandra forbids empty partition keys)
SELECT count(*) FROM datasets_health.big_five_big5_data WHERE country = '__UNKNOWN__';
```

### lastfm (`datasets_music`, partition = `user_id`)
~17M user↔artist play counts + user demographics (no timestamps — it's lifetime counts).
```sql
-- everything a user listened to (partition query)
SELECT artist_name, play_count FROM datasets_music.lastfm WHERE user_id = '<user_id>';

-- a user's top artists
SELECT artist_name, play_count FROM datasets_music.lastfm
WHERE user_id = '<user_id>' ORDER BY row_id;   -- sort client-side by play_count
```

### uci_year_prediction (`datasets_music`, partition = `year`)
515k songs × 90 timbre features, partitioned by release year.
```sql
SELECT count(*) FROM datasets_music.uci_year_prediction WHERE year = '2005';
SELECT * FROM datasets_music.uci_year_prediction WHERE year = '2005' LIMIT 10;
```

### Cassandra-isms
- **Partition key required** for efficient reads. Querying a non-key column needs `ALLOW FILTERING` (full scan —
  fine for a lab, slow at scale). That's *why* we chose meaningful partitions (country / user_id / year).
- `COUNT(*)` is a full-partition scan — cheap within one partition, expensive across all (this is why DataHub
  profiling excludes lastfm).
- No JOINs. Model/denormalize around the query. `SELECT JSON …` returns rows as JSON.
