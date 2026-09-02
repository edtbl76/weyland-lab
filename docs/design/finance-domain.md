# B113 — Financial / economic datasets domain (design + scope)

Status: **SCOPED 2026-09-02** (Linear EMA-110, thread (c) of B78). Full domain, phased build. This is a new **data
domain**, not a new platform — it rides the built data mesh (B1) exactly like the Music and Health domains, via the
same `datasets_lib` machinery. Free, self-hosted open data only (decided 2026-07-31 vs the paid Bigdata.com/RavenPack
route). Read alongside [data-mesh-design.md](data-mesh-design.md) (the L1–L8 platform) and
`docs/data-domain-storage-grid.csv` (the per-dataset tier matrix this domain adds rows to).

## Why this domain

Finance/economics is the richest of the three domains because it maps onto the mesh tiers Music/Health *underuse* —
so it exercises the whole platform rather than repeating it:

- **TimescaleDB** — macro series (FRED) and daily market prices are textbook hypertables; Music/Health barely touch
  Timescale.
- **Vector / RAG** — SEC filing *text* (10-K / 10-Q) → Qdrant / Weaviate / LanceDB → a **filings-RAG notebook** that
  slots straight into the B81 library and the AI/RAG lane.
- **Neo4j** — company → subsidiary → SIC-industry → filing graph.
- **Iceberg / dbt / Trino / ClickHouse** — XBRL structured financials + OLAP.

## Sources → datasets (all free)

| Source | Auth | Dataset | Cadence for the build |
|---|---|---|---|
| **FRED** (St. Louis Fed) | free API key | ~12–15 macro series: real GDP, CPI, core CPI, unemployment rate, Fed funds, 2y/10y treasury yields, 30y mortgage, PCE, industrial production, retail sales, housing starts, M2 | static snapshot (full history) |
| **SEC EDGAR** — company-facts XBRL | none (User-Agent required) | structured financials (revenue, net income, assets, liabilities, EPS, shares) for **~50 curated companies** (e.g. a slice of the S&P 100) | static snapshot |
| **SEC EDGAR** — filings text | none (User-Agent) | 10-K / 10-Q primary documents for those companies (latest 1–2 per company) | static snapshot |
| **Market OHLCV** | free tier | daily open/high/low/close/volume for **~30–50 tickers** (overlapping the EDGAR companies) | static snapshot |

**Market-source caveat (decide at build):** Alpha Vantage's free tier is ~25 requests/day — too tight for 30–50
tickers of history. **Finnhub** (60/min) is better, and for a *static* bulk snapshot a free bulk source
(**stooq** CSV, or `yfinance` off Yahoo) is the pragmatic pick. Recommendation: bulk-snapshot via stooq/yfinance for
the build; keep Finnhub in reserve for any later live-refresh.

## Tier mapping (the storage-grid rows this domain adds)

| Dataset | dbt mart | Iceberg/Trino | Timescale | ClickHouse | Postgres | Neo4j | Vector (Qdrant/Weaviate/LanceDB) | Feast |
|---|---|---|---|---|---|---|---|---|
| FRED macro series | Y (`mart_macro_indicators`) | Y | **Y** (per-series hypertable) | Y (OLAP) | N | N | N | optional |
| EDGAR XBRL financials | Y (`mart_company_financials`) | Y | N | Y | Y | **Y** (company/industry graph) | optional |
| EDGAR filing text | N | Y (metadata) | N | N | N | Y (filing→company link) | **Y** (filings RAG) | N |
| Market OHLCV | Y (`mart_price_daily`) | Y | **Y** (per-ticker hypertable) | Y (OLAP) | N | N | N | optional (returns/vol features) |

## Build shape — walking skeleton, then expand

Mirrors how the mesh itself was built (skeleton first, gated, then the rest):

1. **Phase 1 — FRED skeleton (gate).** One source end-to-end: `datasets_finance_fred_land.py` → silver transform →
   gold Iceberg → Timescale hypertables + Trino + DataHub domain/data-product + a `mart_macro_indicators` dbt mart.
   Proves the finance `DomainConfig`, the Timescale path, and the DataHub domain. Approve before the rest.
2. **Phase 2 — EDGAR XBRL (structured + graph).** company-facts → Iceberg + `mart_company_financials` + Postgres +
   the **Neo4j** company/industry graph.
3. **Phase 3 — EDGAR filings RAG.** filing text → silver → vector stores (Qdrant/Weaviate/LanceDB) → a
   **`63_rag_sec_filings.ipynb`**-style notebook in the B81 library (retrieve over filings, answer with citations).
4. **Phase 4 — market OHLCV.** daily prices → Timescale + Iceberg + ClickHouse + `mart_price_daily`.

## Machinery (reuse, don't reinvent)

Follow the existing `services/weyland-dagster/weyland_pipeline/assets/datasets_lib/` pattern used by Music/Health:
`config.py` (`DomainConfig`), `loaders.py` (`build_store_load_assets` — the Tier-2 fan-out), `checks.py`
(`build_asset_checks`), plus a new `datasets_finance_transform.py` and per-dataset `datasets_finance_*_land.py`
landers with `group_name="datasets_finance"`. The store-load specs declare which tiers each dataset targets (the grid
above). dbt marts go in the dbt project; DataHub emit via the existing emitters.

## Decisions (settled here so the build doesn't re-open them)

- **Domain name:** `finance` / `datasets_finance` (matches `datasets_music` / `datasets_health`).
- **Static snapshots only** for this build; a scheduled live-refresh (and/or a tiny self-built MCP for *current*
  filings/prices) is an explicit **later** item, not in scope now.
- **Secrets:** FRED key + (if used) Finnhub key → gitignored `scripts/.env` for the loader run, then a **SealedSecret**
  for any in-cluster component. EDGAR needs no key but a descriptive **User-Agent** (SEC requirement) — set it.
- **Bounded counts** (lab footprint): ~12–15 FRED series, ~50 companies, ~30–50 tickers — enough to be real, small
  enough to snapshot cheaply on the single node.
- **Contracts = ODCS.** The mesh design already standardizes contracts on ODCS; this domain's data products are the
  natural first ODCS contracts — a direct dependency on **B157** (ODCS eval) and an exerciser of **B156** (the 5
  data-platform capabilities: discovery/observability/control/onboarding/interoperability).

## DoD acceptance criteria (the 8 pillars, applied)

1. **Docs** — arch.md domain row; api.md/hosts.md only if a new endpoint (none expected — reuses stores); a
   `docs/query/finance.md` cookbook; storage-grid rows; platform-map/Port if a new component (none expected).
2. **Diagrams** — LikeC4 only if a new component (likely none); a `flow-finance-ingestion.md` sequence
   (land→silver→gold→fan-out) is required.
3. **Demos** — a `demos/finance-domain.md` (CLI ingestion run + the filings-RAG notebook UI), executed.
4. **Cleanup** — landers/transforms are idempotent; snapshots reproducible; note it.
5. **Tracking** — EMA-110 + backlog; memory for any non-obvious source gotcha (XBRL shapes, EDGAR rate etiquette).
6. **Ops** — Dagster schedule/sensor + freshness for the snapshots; DataHub freshness; the coverage guards see any
   new scraped job; backups N/A (reproducible from source).
7. **Scan** — the new dagster code + any manifest through the scan suite; triage.
8. **Cascade** — **DataHub** (new domain + data products + glossary + column lineage), **dbt** (new marts + tests),
   **data-quality** (Soda/GE checks per dataset), **storage grid** rows, **query cookbook**, and the ODCS contracts.
   This domain is a large Pillar-8 exercise by nature.

## Relations

B1 (the mesh this rides), B77 (DQ — `@asset_check` / GE per dataset), B80 (DataHub maturity), B73 (dataset uses),
**B156** (capability audit — onboarding this domain is the live test of it), **B157** (ODCS — the contract standard
these products adopt). Supersedes the paid-vendor route rejected 2026-07-31.
