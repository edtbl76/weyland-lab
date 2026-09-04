# CockroachDB — query cookbook

**Connect:** pg-wire, insecure (user `root`, no password). Admin UI at `cockroachdb.weyland.lab` (Keycloak).
IntelliJ/DataGrip → CockroachDB (or PostgreSQL) driver, port-forward the `cockroachdb` svc `26257`, `sslmode=disable`.
In-pod: `kubectl -n data-mesh exec -it deploy/cockroachdb -- cockroach sql --insecure`.

**One database per dataset:** `brfss`, `nhis` (US health surveys). Coded columns (cryptic names) — introspect first.

### Explore
```sql
SHOW DATABASES;
SHOW TABLES FROM brfss;
SELECT column_name, data_type FROM information_schema.columns
WHERE table_catalog='brfss' AND table_name='<table>' ORDER BY ordinal_position;
```

### BRFSS (Behavioral Risk Factor Surveillance System, ~3M rows across 6 tables)
Survey codes: `_state` (FIPS), `iyear`/`imonth` (interview date), `_ageg5yr`, `sex`, `genhlth` (general health 1–5).
```sql
-- respondents per state (adapt table/column names from the introspection above)
SELECT _state, count(*) AS n FROM brfss.<table> GROUP BY _state ORDER BY n DESC;

-- self-rated general health distribution (1=Excellent … 5=Poor)
SELECT genhlth, count(*) AS n FROM brfss.<table> GROUP BY genhlth ORDER BY genhlth;

-- interviews by year
SELECT iyear, count(*) AS n FROM brfss.<table> GROUP BY iyear ORDER BY iyear;
```

### NHIS (National Health Interview Survey)
```sql
SHOW TABLES FROM nhis;
SELECT count(*) FROM nhis.<table>;
-- profile a coded column
SELECT <col>, count(*) AS n FROM nhis.<table> GROUP BY <col> ORDER BY n DESC LIMIT 25;
```

### Finance — EDGAR company financials (B113 Phase 2)

`company_financials` (long facts) + `company_meta` (dim) fanned out to CockroachDB (distributed SQL) — the same
tidy silver the OLAP/lakehouse path reads. ~49 mega-caps, 20,741 facts.

```sql
-- revenue history for one company (annual 10-K), pg-wire so standard SQL
SELECT fy, period_end, value AS revenue
FROM company_financials.company_financials
WHERE ticker = 'AAPL' AND concept = 'revenue' AND form = '10-K' AND fp = 'FY'
ORDER BY period_end DESC;

-- companies per SIC industry (join to the dim)
SELECT m.sic_description, count(DISTINCT m.cik) AS companies
FROM company_meta.company_meta m
GROUP BY m.sic_description ORDER BY companies DESC;
```

### Cockroach-isms
- It's Postgres **wire**, not dialect — most `pg_catalog` / `information_schema` works, but the version string
  breaks the SQLAlchemy pg dialect (use `cockroachdb://`). For ad-hoc SQL it behaves like Postgres.
- Admin UI (`cockroachdb.weyland.lab`) → **Databases** shows table/row/range stats without querying.
- Single-node here → no real geo-partitioning; `SHOW RANGES` is mostly academic.
