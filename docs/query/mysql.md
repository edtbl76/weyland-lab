# MySQL — query cookbook

**Connect:** `mysql.data-mesh.svc:3306` (user/dev-password). IntelliJ → MySQL driver, port-forward the `mysql`
svc `3306`. In-pod: `kubectl -n data-mesh exec -it deploy/mysql -- mysql -u<user> -p<pw>`.

**One database per dataset** (table per silver parquet file). Health (6): `nhanes`, `big_five`, `who_gho`,
`cdc_physical_activity`, `brfss`, `nhis`. Finance (2, B113 Phase 2): `company_financials`, `company_meta` —
the database self-provisions on first load (`CREATE DATABASE IF NOT EXISTS` + the `mysql.yaml` `--init-file`
schema grant), so a new domain never needs a per-dataset root grant.

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

### Finance — EDGAR company facts (B113 Phase 2)
`company_financials` (20,741 rows — one XBRL fact per row: `cik, ticker, company, concept, unit, period_end, fy,
fp, form, filed, value`) and `company_meta` (49 rows: `cik, ticker, company, sic, sic_description, exchange`).
```sql
USE company_financials;  SHOW TABLES;   -- table mirrors the silver parquet (company_financials)

-- latest annual Revenue per company (10-K facts; concept is the XBRL tag)
SELECT ticker, company, value, period_end
FROM company_financials.company_financials
WHERE concept IN ('Revenues','RevenueFromContractWithCustomerExcludingAssessedTax')
  AND fp = 'FY'
ORDER BY period_end DESC, value DESC LIMIT 20;

-- one company's fact history for a concept
SELECT fy, period_end, value FROM company_financials.company_financials
WHERE ticker = 'AAPL' AND concept = 'Assets' ORDER BY period_end;

-- companies by industry (SIC)
SELECT sic, sic_description, COUNT(*) AS n
FROM company_meta.company_meta GROUP BY sic, sic_description ORDER BY n DESC;
```

### MySQL-isms
- Column names mirror the source parquet (mixed case; MySQL identifiers are case-insensitive on Linux by
  default but the stored case is preserved).
- These are `to_sql` dumps — no indexes except what `to_sql` created. Add one if a filter is slow:
  `ALTER TABLE t ADD INDEX (col);`
- Superset can chart any of these directly (add the DB as a Superset connection).
