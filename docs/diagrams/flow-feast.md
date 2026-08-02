# Flow — Feast (feature store: offline / online / registry + point-in-time)

Feast is the odd store: not "silver → table," but a **feature store** — the same feature *defined once* and
served two ways. **Offline** (Postgres) for point-in-time-correct training sets; **online** (Valkey) for
low-latency serving by entity key; a **registry** (Postgres) holding the definitions, read on every access.
See [query/feast.md](../query/feast.md) + [runbooks/datasets-hydration.md](../runbooks/datasets-hydration.md).

```mermaid
flowchart TB
  subgraph BUILD["build (scripts/feast_setup.py, in the dagster pod)"]
    SILVER[("lakeFS silver Parquet<br/>spotify_tracks · brfss")]
    LOAD["shape → offline tables<br/>track_audio_features (static + synthetic ts)<br/>state_health_risk (prevalence % per state,year)"]
    SILVER --> LOAD
  end

  subgraph PG["Postgres (feast DB)"]
    OFFLINE[("offline store<br/>source tables + history")]
    REGISTRY{{"registry<br/>feature definitions"}}
  end
  VALKEY[("online store — Valkey<br/>latest value per entity key")]

  LOAD --> OFFLINE
  LOAD -.->|"feast apply"| REGISTRY
  OFFLINE -->|"feast materialize<br/>(offline → online)"| VALKEY

  subgraph SERVE["retrieve"]
    HIST["get_historical_features<br/>POINT-IN-TIME (leakage-free training set)"]
    ONLINE_SDK["get_online_features (SDK)"]
    REST["feast-server REST :6566<br/>feast.weyland.lab · /docs Swagger"]
  end

  OFFLINE -->|"as-of join"| HIST
  VALKEY --> ONLINE_SDK
  VALKEY --> REST
  REGISTRY -.->|"read on every init"| ONLINE_SDK
  REGISTRY -.->|"read on every init"| REST
  REGISTRY -.-> HIST
  REST --> CONSUMER["consumers<br/>Stud.IO (future)"]
  HIST -->|"materialize (meshed Dagster asset<br/>genre_feast_training_set)"| TRAINSET[("lakeFS<br/>music/parquet/genre_feast_training/")]
  TRAINSET -->|"--source feast"| TRAINER["genre-trainer on the Ray worker (rogueone)<br/>→ MLflow (genre_classifier v7)"]

  classDef truth fill:#2d6a4f,stroke:#95d5b2,color:#fff;
  class REGISTRY truth;
```

**The three capabilities Feast adds** (none provided by the other stores):

1. **Low-latency serving by entity key** — `get_online_features(state=CA)` → prevalences in ms from Valkey.
   Vector stores do *similarity*, OLAP does *aggregates*; neither does "give me THIS entity's features, fast."
2. **Point-in-time training retrieval** — `get_historical_features` joins each label **as of its own timestamp**
   (CA-2013 ≠ CA-2019 — no leakage from future surveys). The thing a naive batch join gets wrong. **Now a live
   consumer:** the meshed Dagster asset `genre_feast_training_set` retrieves the genre-classifier's features this
   way → lakeFS → the external Ray trainer fits it (`--source feast` → `genre_classifier` v7). Feast's offline
   store is STRICT-mTLS Postgres, so this retrieval MUST run in-cluster/meshed — the external trainer can't reach
   it. See [../runbooks/mlflow-training.md](../runbooks/mlflow-training.md) UC2.
3. **Registry + train/serve consistency** — one feature definition serves both paths, so training and serving
   can't drift (a `FeatureService` like `recommender_v1` is the unit a consumer requests).

**Two views** demonstrate both halves: `track_audio_features` (entity `track`, static Spotify audio features →
the serving half) and `state_health_risk` (entity `state`, BRFSS chronic-condition prevalence per year →
the point-in-time half).

**Gotchas:**
- **The registry (Postgres) is on the *serving* path** — every `FeatureStore` init reads it, so online serving
  is Valkey **+ Postgres**, not pure Valkey.
- **feast-server is MESHED** (data-mesh, istio-injected) → mTLS to STRICT weyland-postgres; an unmeshed pod gets
  an opaque ECONNRESET (the `postgres-strict-needs-mesh` lesson) + `feast serve` exits on a one-shot startup
  connect, so `holdApplicationUntilProxyStarts` avoids the Envoy race. Slim feast image (not the fat dagster one
  → no OOM). psycopg3 requires `sslmode=disable` (weyland-postgres has TLS off).
- **Don't browse Valkey directly** — features are stored in Feast's binary encoding (serialized keys + protobuf).
- **feast UI (`feast-ui.weyland.lab`) needs a `registry.json` dump, not the REST base.** feast 0.58's bundled UI
  frontend *predates* its own REST backend: it does a single `GET registryPath` expecting a `registry.json` dump,
  but feast hardcodes `registryPath=/api/v1` (served only piecemeal) → **empty UI**. A ConfigMap launcher
  (`k8s/data-mesh/feast-ui.yaml`) runs `feast ui`, then overwrites `projects-list.json` → `/registry.json` and
  generates that dump (`MessageToJson(registry.proto())`) into the served UI dir, refreshed on an interval. Also
  needs `grpcio grpcio-health-checking grpcio-reflection` in the feast image. See backlog **B-RT #5**.

## Sequence

Build/materialize, then the two retrieval paths (online by key, point-in-time historical). Demo: [demos/feast.md](../demos/feast.md).

```mermaid
sequenceDiagram
    actor User
    participant UC as dagster-user-code
    participant Lake as lakeFS silver
    participant PG as Postgres feast DB<br/>(offline + registry)
    participant Valkey as Valkey (online)
    participant Server as feast-server REST<br/>(feast.weyland.lab :6566)

    User->>UC: run scripts/feast_setup.py
    UC->>Lake: read spotify_tracks / brfss silver
    UC->>PG: shape → offline tables
    UC->>PG: feast apply (write registry)
    UC->>Valkey: feast materialize-incremental (offline → online)

    Note over User,Server: online — low-latency by entity key
    User->>Server: POST /get-online-features {state:[CA,NY,TX]}
    Server->>PG: read registry (defs)
    Server->>Valkey: fetch latest per key
    Server-->>User: diabetes_pct / asthma_pct / copd_pct

    Note over User,PG: historical — point-in-time (leakage-free)
    User->>UC: get_historical_features(entity_df + timestamps)
    UC->>PG: read registry + as-of join offline
    PG-->>UC: features as of each row's timestamp
```
