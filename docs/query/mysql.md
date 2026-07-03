# MySQL — query cookbook

**Connect:** `mysql.data-mesh.svc:3306` (user/dev-password). IntelliJ → MySQL driver, port-forward the `mysql`
svc `3306`. In-pod: `kubectl -n data-mesh exec -it deploy/mysql -- mysql -u<user> -p<pw>`.

**One database per dataset** (6): `nhanes`, `big_five`, `who_gho`, `cdc_physical_activity`, `brfss`, `nhis`
(32 tables total; table per silver parquet file).

### Explore
```sql
SHOW DATABASES;
USE who_gho;
SHOW TABLES;
DESCRIBE <table>;
SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema='who_gho';
```

### WHO GHO
```sql
-- life expectancy for a country over time
SELECT TimeDim, NumericValue FROM who_gho.<life_expectancy_table>
WHERE SpatialDim = 'USA' ORDER BY TimeDim;

-- avg indicator by year
SELECT TimeDim AS year, AVG(NumericValue) AS avg_val FROM who_gho.<table>
GROUP BY TimeDim ORDER BY year;
```

### big_five (OCEAN personality)
```sql
-- responses per country
SELECT country, COUNT(*) AS n FROM big_five.<table> GROUP BY country ORDER BY n DESC LIMIT 25;
-- mean of an item (e.g. EXT1) by country
SELECT country, AVG(EXT1) AS mean_ext1 FROM big_five.<table> GROUP BY country ORDER BY mean_ext1 DESC;
```

### BRFSS / NHIS / NHANES / CDC
Coded survey columns — introspect first, then aggregate.
```sql
USE brfss;  SHOW TABLES;
SELECT _STATE, COUNT(*) AS n FROM brfss.<table> GROUP BY _STATE ORDER BY n DESC;   -- respondents per state
SELECT GENHLTH, COUNT(*) AS n FROM brfss.<table> GROUP BY GENHLTH ORDER BY GENHLTH; -- 1=Excellent … 5=Poor
```

### MySQL-isms
- Column names mirror the source parquet (mixed case; MySQL identifiers are case-insensitive on Linux by
  default but the stored case is preserved).
- These are `to_sql` dumps — no indexes except what `to_sql` created. Add one if a filter is slow:
  `ALTER TABLE t ADD INDEX (col);`
- Superset can chart any of these directly (add the DB as a Superset connection).
