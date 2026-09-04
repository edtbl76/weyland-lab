# Demo — Finance domain (B113 Phase 1: FRED macro, land → mart → BI)

The finance data domain riding the mesh, FRED macro slice: ~13 macro series landed end-to-end and served through
the mesh's BI surfaces. Ingestion is the `datasets_lib` three-factory path (same as Music/Health); consumption is
**Lightdash + Superset + Cube** (not Grafana — that's observability). See
[design/finance-domain.md](../design/finance-domain.md), [diagrams/flow-finance-ingestion.md](../diagrams/flow-finance-ingestion.md),
and the finance sections of the per-store [query cookbooks](../query/) (`trino.md`, `dbt-marts.md`, `timescaledb.md`,
`clickhouse.md`, `gizmosql.md`).

## Prerequisites

- `weyland/fred-secret` sealed + present (FRED API key), mounted into `dagster-user-code` as `FRED_API_KEY`.
- `dagster-user-code` running the image with the finance assets (`group:datasets_finance` visible in Dagster).
- Trino/Iceberg, TimescaleDB, ClickHouse, DataHub, Lightdash, Superset, Cube up.

## CLI walkthrough — ingest the FRED slice

Materialize in Dagster (UI: **Assets → select group → Materialize**, or GraphQL `launchRun` on `__ASSET_JOB`).
Idempotent — a static full-history snapshot, safe to re-run.

1. **Land + transform (silver + gold):** materialize `group:datasets_finance`
   → `datasets_finance_fred_land` fetches **13 series / 40,930 observations** (FRED `"."` missing → NULL),
   then `parquet/arrow/avro/lance` silver + `iceberg` gold + the Nessie `commit`.
   Expect: 7 materializations, `series_ok=13`, `macro_rows=40,930`, `value` nulls ≈ 1,273.
2. **Store fan-out:** materialize `group:datasets_finance_stores`
   → `timescaledb_load` (hypertable `fred_macro`, 40,930 rows) + `clickhouse_load` (`fred_macro` 40,930 +
   `fred_series_meta` 13).
3. **dbt mart:** materialize `mart_macro_indicators`
   → `iceberg.dbt.mart_macro_indicators` — one row per series with `latest_value`, `prior_year_value`, `yoy_pct`.
4. **Catalog emit:** run `datahub_catalog_emit_job`
   → DataHub domain **Finance**, data product **Macro Indicators**, glossary **Finance Concepts** + 4 terms.

## Eyes-on UAT — confirm each surface renders the right data

**Trino (the source of truth for BI):**
```sql
SELECT series_id, title, latest_value, round(yoy_pct,2) AS yoy_pct
FROM iceberg.dbt.mart_macro_indicators ORDER BY series_id;
```
Confirm 13 rows: CPI ~332.8 (+3.3%), Unemployment 4.1% (−4.7%), Fed Funds 3.63% (−16.2%), Real GDP ~24,269.6 (+2.1%).

**Lightdash** — `https://lightdash.weyland.lab` → **Finance — marts overview**. Confirm the *Macro indicators —
latest value & YoY* table lists all 13 series with units, and the *Year-over-year change by indicator* bar shows
positive bars green-ward / negative (Fed Funds, Unemployment, Housing) the other way.

**Superset** — `https://superset.weyland.lab` → Dashboards → **Weyland Marts — Finance**. Confirm *Macro YoY by
indicator* and *Macro latest value by indicator* bars render over the `mart_macro_indicators` Trino dataset.

**Cube** — the `macro_indicators` cube (measures `count`, `latest_value`, `avg_yoy_pct`; dimensions `series_id`,
`title`, `units`, `frequency`, `seasonal_adjustment`). Check via the semantic-layer notebook (`41_semantic_cube.ipynb`)
or the Cube SQL API: `SELECT series_id, measure(avg_yoy_pct) FROM macro_indicators GROUP BY 1`.

**DataHub** — `https://datahub.weyland.lab` → Domains → **Finance** (21 assets) and Data Products → **Macro
Indicators** (8 assets); Glossary → **Finance Concepts** (Macro-Economic Indicator, YoY, Seasonal Adjustment,
Treasury Yield).

## Phase 2 — SEC EDGAR (structured financials + company graph)

Materialize `datasets_finance_edgar_land` (force it — freshness-gated) → transform → stores → dbt → graph:

1. **Land** `group:datasets_finance` (force) → `datasets_finance_edgar_land` fetches ~50 mega-caps' company-facts +
   submissions (User-Agent required) → **20,741 fact rows** (`company_financials`) + `company_meta` +
   **1,144** `company_filings` (10-K/10-Q). Foreign filers (ASML/BABA) yield 0 us-gaap facts — expected.
2. **Stores + mart:** `group:datasets_finance_stores` (ClickHouse + CockroachDB + MySQL + MongoDB — each 20,741
   facts / 49 dims; MySQL dbs self-provision, Mongo dates encode as timestamps) + `mart_company_financials` (dbt).
3. **Graph:** `datasets_finance_neo4j_load` → `(:Company)-[:IN_INDUSTRY]->(:SIC)` + `(:Company)-[:FILED]->(:Filing)`.
4. **Catalog:** `datahub_catalog_emit_job` → DataHub **Company Financials** product.

**Eyes-on UAT:**
- **Trino:** `SELECT ticker, revenue, net_income, eps_basic FROM iceberg.dbt.mart_company_financials ORDER BY revenue DESC` — AAPL/AMZN/MSFT/NVDA with real FY values.
- **Neo4j** (`https://neo4j.weyland.lab`): the semiconductor peer group + filing counts (see [query/neo4j.md](../query/neo4j.md)).
- **Lightdash:** `Finance — company financials` dashboard. **Superset:** the company charts on `Weyland Marts — Finance`.
- **Cube:** the `company_financials` cube (`SELECT company_financials.total_revenue`).
- **DataHub:** Domains → Finance (39 assets); Data Products → Company Financials (20).

## Phase 3 — SEC EDGAR filings-text RAG

The narrative half of EDGAR: each company's **latest 10-K** text, section-aware chunked → the vector stores → a
retrieval-with-citations notebook.

1. **Land** `datasets_finance_edgar_text_land` (force — freshness-gated) → fetches each US filer's latest 10-K
   primary document, strips the HTML (bs4), and chunks it **section-aware** (`edgar_text_parse`: Business / Risk
   Factors / Legal Proceedings / MD&A / Market Risk, whole-doc fallback) → `filings_text` (~a few thousand
   chunks; ~40 filers — foreign 20-F filers like ASML/BABA yield no 10-K, expected).
2. **Silver + gold + vectors:** `group:datasets_finance` writes `filings_text` silver/Iceberg; then
   `group:datasets_finance_stores` runs the vector fan-out — `datasets_finance_qdrant_load` /
   `_weaviate_load` / `_lancedb_load` embed the `text` column with **bge-small (384)** into collection
   `datasets_finance_filings_text` (payload carries ticker / accn / section / chunk_id for citations).
3. **Catalog:** `datahub_catalog_emit_job` → DataHub **SEC Filings** product (Finance domain).

**Eyes-on UAT:**
- **Notebook** `63_rag_sec_filings.ipynb` (JupyterHub) — ask a cross-company question ("supply-chain / component
  risks"), see the top-k 10-K chunks (ticker · section · snippet), the **grounded answer with `[n]` citations**
  via `wl-rag`, the no-context contrast, and the **Risk-Factors-only** section-filtered retrieval.
- **Trino:** `SELECT ticker, section, count(*) FROM iceberg.datasets_finance.filings_text GROUP BY 1,2 ORDER BY 1,2`
  — the section distribution per company.
- **Qdrant** (`qdrant.weyland.lab`): collection `datasets_finance_filings_text` populated, dim 384. See
  [query/qdrant.md](../query/qdrant.md).

## Expected result

The 13 FRED macro series are queryable across Iceberg/Trino, TimescaleDB, and ClickHouse; the dbt mart serves
latest-value + YoY; three BI surfaces render it; DataHub catalogs the domain, product, and glossary. Grafana is
intentionally **not** a finance surface.

## Cleanup / teardown

Nothing to tear down — the snapshot is idempotent and reproducible from FRED. Re-materializing `group:datasets_finance`
refreshes it in place. Stores are truncate-and-reload on the store-load assets.
