# Flow — Finance domain ingestion (FRED macro: land → silver → gold → fan-out → mart → BI)

The **finance** data domain (B113 Phase 1) riding the `datasets_lib` platform, same three-factory shape as
Music/Health — a `FINANCE_CFG` `DomainConfig` fed through **transform → asset-checks → store-load**. This is the
FRED macro slice: ~13 macro series (GDP, CPI, unemployment, Fed funds, treasury yields, M2, PCE, …), static
full-history snapshot. See [design/finance-domain.md](../design/finance-domain.md),
the per-store [query cookbooks](../query/) (finance sections in `trino.md` / `dbt-marts.md` / `timescaledb.md` /
`clickhouse.md` / `gizmosql.md`), and the generic [flow-datasets-lakehouse.md](flow-datasets-lakehouse.md).

```mermaid
flowchart TB
  subgraph SRC["source"]
    FRED["FRED API<br/>api.stlouisfed.org<br/>free key · User-Agent"]
  end

  LAND["datasets_finance_fred_land<br/>13 series · 40,930 obs<br/>&quot;.&quot; → NULL coerce"]
  RAW[("lakeFS raw/ — BRONZE<br/>fred_macro · fred_series_meta")]

  subgraph LIB["datasets_lib — FINANCE_CFG, three factories"]
    T["build_transform_assets<br/>reader dispatch · name-normalize · null-coerce"]
    C["build_asset_checks<br/>@asset_check gate"]
    L["build_store_load_assets<br/>silver Parquet → store"]
  end

  subgraph SILVER["SILVER — lakeFS"]
    PQ["parquet"]
    AR["arrow"]
    AV["avro"]
    LN["lance"]
  end
  GOLD[("Iceberg GOLD — Nessie<br/>datasets_finance.fred_macro (40,930×3)<br/>datasets_finance.fred_series_meta (13×5)")]

  subgraph STORES["Tier-2 stores (Phase 1)"]
    TS["TimescaleDB<br/>fred_macro hypertable (date)"]
    CH["ClickHouse<br/>fred_macro + fred_series_meta"]
  end

  MART["dbt · iceberg.dbt.mart_macro_indicators<br/>latest value + YoY per series"]

  subgraph BI["Consumption (L6/L7) — NOT Grafana"]
    LD["Lightdash<br/>finance-marts-overview"]
    SS["Superset<br/>Weyland Marts — Finance"]
    CU["Cube<br/>macro_indicators cube"]
  end

  DH["DataHub<br/>domain Finance (21) · product Macro Indicators (8)<br/>glossary · Soda assertions"]

  FRED --> LAND
  LAND --> RAW
  RAW --> T
  T --> PQ
  T --> AR
  T --> AV
  T --> LN
  T --> GOLD
  T --> C
  PQ --> L
  C -. gates .-> L
  L --> TS
  L --> CH
  GOLD --> MART
  MART --> LD
  MART --> SS
  MART --> CU
  PQ --> DH
  GOLD --> DH
  MART --> DH
```

**Layers:** land (bronze) → transform (silver + gold) → quality gate → store hydration → dbt mart → BI. The FRED
missing-observation sentinel (`.`) is coerced to NULL in the lander, so `fred_macro.value` carries genuine gaps
(1,273 nulls) that the Soda check tolerates (`missing_percent(value) < 100`, never non-null). BI is **Lightdash +
Superset + Cube** over the mart — Grafana is the observability plane and carries no finance analytics.

**Deferred (static build):** streaming/live-refresh (Redpanda/Avro), and Cassandra/Postgres/graph tiers arrive
with the later phases (EDGAR XBRL, filings RAG, market OHLCV) per the design doc.

## Sequence

The runtime order for the FRED slice through the factories (as executed in Phase 1). Demo:
[demos/finance-domain.md](../demos/finance-domain.md).

```mermaid
sequenceDiagram
    actor User
    participant Dagster as Dagster<br/>(dagster.weyland.lab)
    participant UC as dagster-user-code
    participant FRED as FRED API
    participant Lake as lakeFS
    participant Ice as Iceberg / Nessie
    participant TS as Timescale + ClickHouse
    participant DH as DataHub

    User->>Dagster: materialize group:datasets_finance
    Dagster->>UC: launchRun (fred_land, freshness-gated)
    UC->>FRED: fetch 13 series (obs + meta)
    UC->>Lake: put raw/ BRONZE (coerce "." to NULL)
    UC->>Lake: transform → silver parquet/arrow/avro/lance
    UC->>Ice: write gold datasets_finance.*
    User->>Dagster: materialize group:datasets_finance_stores
    Dagster->>UC: launchRun (timescale + clickhouse load)
    UC->>TS: load fred_macro (40,930) + meta (13)
    User->>Dagster: materialize mart_macro_indicators (dbt)
    UC->>Ice: build iceberg.dbt.mart_macro_indicators
    User->>Dagster: run datahub_catalog_emit_job
    UC->>DH: emit domain + product + glossary + Soda
```

## Phase 2 — SEC EDGAR (structured financials + company graph)

Same three-factory path for the EDGAR slice, plus a Neo4j graph. `company_financials` (long facts) +
`company_meta` (dim) fan out to the tabular/OLAP stores + the `mart_company_financials` mart;
`company_filings` is graph-only.

```mermaid
flowchart TB
  SEC["SEC EDGAR<br/>company-facts XBRL + submissions<br/>~49 mega-caps · User-Agent"]
  LAND["datasets_finance_edgar_land<br/>company_financials (20,741) · company_meta (49) · company_filings (1,144)"]
  GOLD[("Iceberg gold<br/>datasets_finance.company_*")]
  subgraph STORES["stores"]
    CH["ClickHouse"]
    CR["CockroachDB"]
    MY["MySQL"]
    MO["MongoDB"]
  end
  MART["dbt · mart_company_financials<br/>latest-annual per company"]
  subgraph GRAPH["Neo4j"]
    G["(:Company)-[:IN_INDUSTRY]->(:SIC)<br/>(:Company)-[:FILED]->(:Filing)"]
  end
  BI["Lightdash · Superset · Cube"]
  DH["DataHub<br/>Company Financials product (20)"]

  SEC --> LAND --> GOLD
  GOLD --> CH
  GOLD --> CR
  GOLD --> MY
  GOLD --> MO
  GOLD --> MART --> BI
  LAND -.company_meta + company_filings.-> G
  GOLD --> DH
  MART --> DH
```

`company_financials` + `company_meta` fan out to **five** tabular/document/OLAP stores — ClickHouse,
CockroachDB, MySQL, MongoDB, and the Iceberg gold — all 20,741 facts + 49 dims. The MySQL and MongoDB loaders
were once blocked on general (not finance-specific) defects, now FIXED: the MySQL loader self-provisions its
database (`CREATE DATABASE IF NOT EXISTS` + the `--init-file` schema grant, so no per-dataset root grant), and
the MongoDB loader casts date columns to timestamp so BSON can encode them (`mongo_encode.to_bson_encodable`).

## Phase 3 — SEC EDGAR filings-text RAG (narrative → vectors → citations)

The narrative half of EDGAR: each company's latest **10-K** text, section-aware chunked, embedded, and served
through the mesh's RAG lane. Structured facts stay in the Phase-2 mart; this is the prose.

```mermaid
flowchart TB
  SEC["SEC EDGAR<br/>latest 10-K primary doc (HTML)<br/>~40 US filers · User-Agent"]
  LAND["datasets_finance_edgar_text_land<br/>bs4 strip → edgar_text_parse<br/>section-aware chunks (whole-doc fallback)"]
  SILVER[("filings_text silver<br/>cik·ticker·accn·section·chunk_id·text")]
  GOLD[("Iceberg gold<br/>datasets_finance.filings_text")]
  subgraph VEC["vector stores (bge-small 384)"]
    QD["Qdrant<br/>datasets_finance_filings_text"]
    WV["Weaviate"]
    LN["LanceDB"]
  end
  NB["63_rag_sec_filings.ipynb<br/>retrieve → cite → answer (wl-rag)<br/>+ section-filtered retrieval"]
  DH["DataHub<br/>SEC Filings product"]

  SEC --> LAND --> SILVER
  SILVER --> GOLD
  SILVER --> QD
  SILVER --> WV
  SILVER --> LN
  QD --> NB
  SILVER --> DH
```

Only the narrative Items (Business / Risk Factors / Legal Proceedings / MD&A / Market Risk) are emitted — the
numbers already live in `company_financials`, so Item 8's tables would dilute a text-RAG corpus. Section
detection anchors on the canonical Item titles and takes each item's **last** occurrence (skipping the
table-of-contents duplicate), validated against a real Apple 10-K; a filing where fewer than two sections
resolve falls back to whole-document chunking rather than silently dropping it. Each chunk's payload carries
`ticker`/`accn`/`section`/`chunk_id` so a retrieval hit is a **citation**, and the `section` tag lets the
notebook scope retrieval to (say) Risk Factors alone.

## Phase 4 — market OHLCV (daily prices → time-series stores → mart)

Daily price bars for the same ~50 mega-caps — the archetypal time-series slice, so it leads with a Timescale
hypertable (like FRED) and adds Cassandra, the one net-new store for the domain.

```mermaid
flowchart TB
  YF["yfinance (Yahoo chart API)<br/>full daily history · ~50 tickers<br/>(stooq CSV now JS-PoW-walled)"]
  LAND["datasets_finance_market_land<br/>market_parse: drop NaN/in-progress bars<br/>price_daily (ticker·date·OHLC·adj_close·volume)"]
  GOLD[("Iceberg gold<br/>datasets_finance.price_daily")]
  subgraph STORES["time-series + OLAP stores"]
    TS["TimescaleDB<br/>hypertable on date"]
    CH["ClickHouse"]
    CA["Cassandra<br/>partition by ticker"]
  end
  MART["dbt · mart_price_daily<br/>latest close · daily return · 30d vol · 52w hi/lo"]
  BI["Lightdash · Superset · Cube"]
  DH["DataHub<br/>Market Prices product"]

  YF --> LAND
  LAND --> GOLD
  LAND --> TS
  LAND --> CH
  LAND --> CA
  GOLD --> MART --> BI
  GOLD --> DH
  MART --> DH
```

The lander drops the in-progress bar (yfinance returns today's row with a NaN close) so no NaN price reaches the
hypertable or poisons the mart's returns/volatility; `auto_adjust=False` keeps both the raw close and the
split/dividend-adjusted `adj_close`. Cassandra keys as `((ticker), row_id uuid)` — one company's whole history
in one partition, a synthetic uuid clustering column keeping every bar unique.

**Deferred / tracked:** ODCS contracts (B157); the ML lane (Phase 5 — a returns/volatility model over these prices).
