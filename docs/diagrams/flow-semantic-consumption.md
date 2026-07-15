# Flow — Semantic + consumption layer (marts → Cube / MetricFlow → BI / notebooks)

The "last mile" of the mesh: how the **7 dbt marts** (the curated gold, in `iceberg.dbt`) reach a human or an app.
Two governed-metric paths (**Cube** L6, **MetricFlow**) plus the direct BI/notebook consumers. Everything routes to
Trino — the marts are Iceberg tables, Trino is the one engine that reads them. See
[query/cube.md](../query/cube.md), [runbooks/cube.md](../runbooks/cube.md),
[runbooks/jupyterhub.md](../runbooks/jupyterhub.md), `[[cube-semantic-layer-b1.7]]`.

```mermaid
flowchart TB
  MARTS[("dbt marts — iceberg.dbt.mart_*<br/>7 tested tables (curated gold)")]

  subgraph TRINO["Trino (federated query engine)"]
    NOAUTH["trino-noauth proxy<br/>(strips Basic-auth; for tools that force a password)"]
    TAUTH["trino.weyland.lab<br/>(IntelliJ / CLI)"]
  end
  MARTS --> TRINO

  subgraph SEM["semantic layer (L6 — governed metrics, defined once)"]
    CUBE["Cube<br/>SQL :15432 · REST/GraphQL :4000<br/>7 cubes · MEASURE() required"]
    MF["MetricFlow (dbt Semantic Layer)<br/>mf query · time-spined health metrics"]
  end
  NOAUTH --> CUBE
  MARTS -.->|"compiles to Trino SQL"| MF

  subgraph BI["BI / apps"]
    SUPERSET["Superset<br/>Cube virtual datasets (MEASURE) + ad-hoc SQL"]
    LIGHTDASH["Lightdash<br/>dbt-native metrics/explores"]
  end
  CUBE -->|"pg-wire :15432"| SUPERSET
  NOAUTH --> LIGHTDASH
  TAUTH --> SUPERSET

  subgraph NB["notebooks (L8)"]
    JHUB["JupyterHub → jupyter-&lt;user&gt; pod<br/>polars · s3fs · duckdb · pylance"]
  end
  MARTS -.->|"lakeFS silver (4 formats)"| JHUB
  TAUTH -.-> JHUB

  CUBE -->|"JWT REST/GraphQL"| APPS["apps / agents (future)<br/>Hermes tool · Stud.IO"]

  classDef gold fill:#2d6a4f,stroke:#95d5b2,color:#fff;
  class MARTS gold;
```

## The two governed-metric paths (and why two)

Both let you **define a metric once** instead of re-deriving `AVG(danceability)` in every chart — but they serve
different consumers:

- **Cube (L6)** — a **headless API** (SQL / REST / GraphQL). Any pg client or app hits it; the SQL API's one rule is
  `MEASURE(measure)` (a bare measure column is rejected). Superset consumes it via `MEASURE()` virtual datasets. It's
  the metric layer an *application or agent* calls. Connects to Trino through the `trino-noauth` proxy.
- **MetricFlow** — the **dbt Semantic Layer** built into the dbt project (`semantic_models.yml`). Metrics compile to
  Trino and are queried with `mf query`. Needs a DAY time-spine (`metricflow_time_spine`), so it's scoped to the
  **time-shaped health marts** (`year` → a date axis); the categorical music marts aren't a fit. It's the metric
  layer a *dbt/analytics workflow* calls.

## The direct consumers (no semantic layer)

- **Superset** — reads Cube (governed) AND raw Trino tables (ad-hoc SQL Lab). The Cube dashboard is seeded by
  `scripts/superset_seed_cube.py`.
- **Lightdash** — dbt-native BI; its own metrics/explores over the marts, via `trino-noauth`.
- **JupyterHub (L8)** — on-demand JupyterLab pods read the marts either through Trino OR straight from the **lakeFS
  silver** in all 4 formats (Parquet/Arrow/Avro/Lance) with the baked polars/duckdb toolkit. This is the
  code-first, exploratory consumer — no metric governance, full flexibility.

## Why it all funnels through Trino

The marts are **Iceberg tables on Nessie** — there's no separate serving DB. Trino is the read path for every
consumer, so the semantic layers (Cube, MetricFlow) and BI tools all connect to Trino (Cube/Lightdash via the
`trino-noauth` auth-strip proxy, since both force a password that no-auth Trino would 401). JupyterHub is the one
consumer that can *also* bypass Trino and read the lakeFS object store directly — useful when you want the raw file,
not a query result.

## Sequence

A governed metric served two ways (Cube API, MetricFlow) and a BI face — all compiling to Trino over the marts.
Demo: [demos/semantic-consumption.md](../demos/semantic-consumption.md).

```mermaid
sequenceDiagram
    actor User
    participant Cube as Cube<br/>(SQL :15432 / REST :4000)
    participant MF as MetricFlow (mf query)
    participant Proxy as trino-noauth proxy
    participant Trino as Trino
    participant Marts as dbt marts<br/>(iceberg.dbt.mart_*)
    participant LD as Lightdash

    Note over User,Marts: Cube — governed metric API
    User->>Cube: SELECT track_genre, MEASURE(avg_danceability) FROM spotify_audio
    Cube->>Proxy: compiled SQL (Basic-auth header)
    Proxy->>Trino: strip Authorization → X-Trino-User: dbt
    Trino->>Marts: read mart_spotify_audio
    Trino-->>Cube: rows
    Cube-->>User: governed metric value

    Note over User,Marts: MetricFlow — dbt Semantic Layer
    User->>MF: mf query --metrics life_expectancy --group-by metric_time__year
    MF->>Trino: compiled Trino SQL (time-spined)
    Trino->>Marts: read mart_country_health
    Trino-->>MF: rows
    MF-->>User: metric by year

    Note over User,LD: BI face (dbt-native)
    User->>LD: open explore / metric
    LD->>Proxy: dbt-compiled SQL
    Proxy->>Trino: forward
    Trino-->>LD: rows → chart
```
