# Flow — Finance domain ingestion (FRED macro: land → silver → gold → fan-out → mart → BI)

The **finance** data domain (B113 Phase 1) riding the `datasets_lib` platform, same three-factory shape as
Music/Health — a `FINANCE_CFG` `DomainConfig` fed through **transform → asset-checks → store-load**. This is the
FRED macro slice: ~13 macro series (GDP, CPI, unemployment, Fed funds, treasury yields, M2, PCE, …), static
full-history snapshot. See [design/finance-domain.md](../design/finance-domain.md),
[query/finance.md](../query/finance.md), and the generic [flow-datasets-lakehouse.md](flow-datasets-lakehouse.md).

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
