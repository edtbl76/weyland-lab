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

## Tier mapping — the storage-grid rows this domain adds (FULL fan-out)

Like Music/Health (each dataset hits 6–11 tiers deliberately, to demonstrate every store with domain-appropriate
data), the finance datasets fan out broadly — this is why it's the biggest domain. Silver is always Arrow/Parquet on
lakeFS; gold is Iceberg. `Y*` = the *natural-fit / showcase* tier for that dataset.

| Tier (grid col) | FRED macro | EDGAR XBRL | EDGAR filing text | Market OHLCV |
|---|---|---|---|---|
| **dbt mart** | Y* `mart_macro_indicators` | Y* `mart_company_financials` | N (metadata only) | Y* `mart_price_daily` |
| **Arrow** (silver) | Y | Y | Y | Y |
| **Iceberg/Trino** | Y | Y | Y (metadata + text ref) | Y |
| **DuckDB/GizmoSQL** | Y | Y | Y | Y |
| **TimescaleDB** | Y* hypertable/series | N | N | Y* hypertable/ticker |
| **ClickHouse** | Y OLAP | Y OLAP | N | Y* OLAP |
| **Postgres** | N | Y | N | N |
| **MySQL** | N | Y (relational financials) | N | N |
| **MongoDB** | N | Y (raw company-facts JSON docs) | Y (filing docs) | N |
| **CockroachDB** | N | Y (distributed-SQL financials) | N | Y (geo/ticker-partitioned) |
| **Cassandra** | Y (wide-column series) | N | N | Y* (ticker-partitioned OHLCV) |
| **OpenSearch** | N | N | Y* (filings **full-text** search) | N |
| **Qdrant / Weaviate / LanceDB** | N | N | Y* (filings **vector RAG**) | N |
| **Neo4j** | N | Y* (company→subsidiary→SIC→filing graph) | Y (filing→company edge) | N |
| **Redpanda / Avro/Kafka** | later (live-refresh) | later | later | later (tick/price stream) |
| **Lance** | N | N | Y (embedding store) | N |
| **Feast** | N | optional | N | Y (returns/vol features) |
| **MLflow** | optional | optional | optional | Y* (a returns/vol model — the ML showcase) |

## Consumption & serving (L6/L7) — the "usable, not just stored" layer (was missing)

The domain isn't done when data lands — it's done when someone can *see* it. This tier was absent from the first cut.

> **Correction (2026-09-03):** the first version of this section named **Grafana** as a finance BI surface. That was
> wrong and contradicts the actual architecture. In this lab **Grafana is the observability plane** (cluster/node/pod
> + pipeline metrics; `arch.md` "Prometheus + Grafana … observability"); it carries **no data-domain analytics**, and
> Music/Health have none there. Every domain's BI lives in **Lightdash + Superset** (+ **Cube** as the headless
> semantic layer). Finance follows that exactly. The section also claimed Lightdash/Superset are KEDA scale-to-zero —
> they are not; both are always-on Helm services.

- **L6 Semantic — Cube + MetricFlow.** A **Cube** cube over the finance marts (`avg` yields, YoY CPI, revenue-growth,
  price-return measures) + MetricFlow metric defs — governed finance metrics, queried via SQL/REST. Every Music/Health
  mart already has a cube (`k8s/cube/cube.yaml`); finance adds one per mart for parity.
- **L7 BI / Dashboards — Lightdash + Superset (NOT Grafana):**
  - **Lightdash** (dbt-native) — a `finance-marts-overview` dashboard + per-mart charts built from the dbt project's
    `meta.metrics`, over Trino through the `trino-noauth` proxy — mirrors `health-marts-overview.yml` /
    `music-marts-overview.yml` under `dbt/lightdash/`.
  - **Superset** — the finance marts registered as Trino datasets (schema `dbt`) with bar/line charts + a finance
    dashboard, seeded by `scripts/superset_seed.py` (the marts seeder), exactly as the 7 Music/Health marts are.
  Both are always-on Helm services (no KEDA). **Each dashboard is an eyes-on UAT surface (DoD Pillar 3).**

## Governance & ML (L5 / L8)

- **L5 Ranger** — a natural finance masking showcase: mask a sensitive/derived financial column for a non-privileged
  Trino user (like the health `depression_pct` mask), demonstrating column-level authz on the finance marts.
- **L5 Soda / GE** — DQ checks per dataset (freshness on series, non-null financial keys, XBRL value ranges).
- **L8 ML lane** — a small **returns/volatility model** on the market data: Feast features → Ray training → MLflow
  registry — the finance analogue of the genre classifier, exercising the whole feature/ML tier.
- **L8 JupyterHub** — the **filings-RAG notebook** (Phase 3) + a finance analysis notebook, folded into the B81
  library.

## Deferred (explicit N/A for the static build, noted so the gap is a decision not an omission)

- **Streaming (Redpanda/Avro + Flink)** — only earns its keep with a **live-refresh** (intraday prices, new
  filings). The static-snapshot build does NOT stand it up; it's the first item of the deferred live-refresh phase.
- **Live-refresh / self-built MCP** — deferred (per the sources decision); the free APIs (FRED/Finnhub/EDGAR)
  support it later without a paid vendor.

## Build shape — walking skeleton, then expand

Mirrors how the mesh itself was built (skeleton first, gated, then the rest):

1. **Phase 1 — FRED skeleton (gate).** One source end-to-end: `datasets_finance_fred_land.py` → silver transform →
   gold Iceberg → Timescale hypertables + Trino + DataHub domain/data-product + a `mart_macro_indicators` dbt mart.
   Proves the finance `DomainConfig`, the Timescale path, and the DataHub domain. Approve before the rest.
2. **Phase 2 — EDGAR XBRL (structured + graph).** company-facts → Iceberg + `mart_company_financials` + Postgres +
   the **Neo4j** company/industry graph.
3. **Phase 3 — EDGAR filings RAG.** filing text → silver → vector stores (Qdrant/Weaviate/LanceDB) → a
   **`63_rag_sec_filings.ipynb`**-style notebook in the B81 library (retrieve over filings, answer with citations).
4. **Phase 4 — market OHLCV.** daily prices → Timescale + Iceberg + ClickHouse + Cassandra + `mart_price_daily`.
5. **Phase 5 — ML lane.** a returns/volatility model on the market data: Feast features → Ray training → MLflow
   registry (the finance genre-classifier analogue).

**Each phase ships its consumption surface, not just storage** — the domain is only "done" when it's usable:
Phase 1 → **Lightdash + Superset macro dashboards** + a Cube macro cube; Phase 2 → **Lightdash/Superset
company-financials dashboards**; Phase 3 → the **filings-RAG notebook** (B81); Phase 4 → **Lightdash/Superset price
dashboards** + the broad Tier-2 fan-out; Phase 5 → the model in the MLflow registry. Ranger masking + Soda/GE checks
land with the marts they govern. So a "phase done" = landed + stored across its tiers + a dashboard/notebook a human
can put eyes on. (BI is always Lightdash/Superset — never Grafana, which is observability-only.)

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
   finance sections in the per-store query cookbooks (`query/trino.md`, `dbt-marts.md`, `timescaledb.md`,
   `clickhouse.md`, `gizmosql.md` — the cookbooks are one-file-per-store, NOT per-domain); storage-grid rows;
   platform-map/Port if a new component (none expected).
2. **Diagrams** — LikeC4 only if a new component (likely none); a `flow-finance-ingestion.md` sequence
   (land→silver→gold→fan-out) is required.
3. **Demos** — a `demos/finance-domain.md`: CLI ingestion run + **eyes-on UAT of every consumption surface** (the
   Lightdash macro/company-financials dashboards, the Superset finance dashboard, the Cube measures, the filings-RAG
   notebook) — a UI is a deliverable, so each dashboard gets explicit "click here, confirm it renders the right data"
   steps. Executed, not just written.
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
