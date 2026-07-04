# Datasets hydration — silver → Tier-2 stores (data-store-mageddon)

The third `datasets_lib` factory. After the transform builds silver/gold (see
[datasets-lake.md](datasets-lake.md)), **`build_store_load_assets(cfg)`** reads the silver **Parquet**
from lakeFS and loads it into the Tier-2 stores the storage grid targets — one loader asset per store,
driven by **explicit per-store allowlists** on `DomainConfig`. A store gets a loader asset only when its
allowlist is non-empty, so the same factory call produces exactly the loaders a domain needs and nothing more.

```text
lakeFS  parquet/<dataset>/<file>.parquet   (silver)
        │
        │  build_store_load_assets(cfg)        ← reads cfg.<store>_allow
        ▼
   datasets_<domain>_<store>_load  (one asset per targeted store)
        │   batched: pyarrow iter_batches → pandas → store write
        ▼
   MySQL · (ClickHouse · Cassandra · CockroachDB · Mongo · Neo4j · OpenSearch · Qdrant · Weaviate · Feast …)
```

Three factories now ride one `DomainConfig`:
`build_transform_assets` → `build_asset_checks` → `build_store_load_assets`.

## Per-store discipline (the two standing calls)

Before building any store's loader, answer two questions (and gate on them):
1. **Where's the real data source?** — almost always the silver **Parquet** (`parquet/<dataset>/`). Loaders
   read Parquet, not raw, so they inherit the cleaning (name-normalize, null-coerce) and the quality checks.
2. **Always-on or KEDA'd?** — `kubectl -n data-mesh get scaledobject,deploy | grep -i <store>`. A
   `ScaledObject` means the loader must trigger/await scale-up; a plain `Deployment` means load directly.

The loader asset `deps` on `datasets_<domain>_parquet`, so it runs after silver exists and the parquet
**`no_failures`** blocking check gates it — bad silver never hydrates.

## Completeness gate — run after EVERY store (not "it ran once")

A store is not done when the loader goes green once. Before marking a store complete, verify all seven —
and record the result (the gate exists to surface the gaps a single successful run hides):

| # | Check | How |
|---|---|---|
| 1 | **Loaded** — every target dataset present, row counts sane | `information_schema` counts vs the `<store>_allow` set |
| 2 | **Runnable** — a hydrate **job** (schedulable), not just a materializable asset | `define_asset_job` selecting the store loader |
| 3 | **Gated** — the parquet `no_failures` check gates the load (bad silver can't hydrate) | loader `deps` on `datasets_<domain>_parquet` |
| 4 | **Cataloged** — DataHub lineage silver → store | emit from the loader (or a native store source) |
| 5 | **Monitored** — store health + load-failure alert | Uptime Kuma monitor + Loki/Alertmanager rule |
| 6 | **Documented** — runbook + arch/hosts/api | this file + arch.md §7 + hosts.md/api.md |
| 7 | **Pushed** — code + manifests (GitOps) | git push; Argo for k8s manifests |

### MySQL — gate result (2026-07-01, punch-list closed → pending deploy+verify)
- ✅ **1 Loaded** — 32 tables, all 6 DBs.
- ✅ **2 Runnable** — `weyland_datasets_health_hydrate_job` (group `datasets_health_stores`; loaders live in
  their own group so the transform job never runs them).
- ✅ **3 Gated** — the loader `deps` on `datasets_health_parquet`; its blocking `no_failures` check gates hydration.
- ✅ **4 Cataloged** — `emit_mysql()` (platform `mysql`, schema from information_schema, lineage ← the
  `datasets.<db>` parquet silver) wired into the hourly `datahub_catalog_emit_job`.
- ~ **5 Monitored** — Loki **`WeylandDatasetHydrationFailure`** rule → Alertmanager → Telegram (catches even
  a single swallowed per-table failure). Store-*up* monitoring via Uptime Kuma is blocked by Kuma's LAN-DNS
  (can't resolve `*.svc.cluster.local`, see [[kuma-lan-dns-monitors]]); MySQL is always-on + meshed, so a
  proper up-monitor = a Prometheus `mysqld-exporter` (deferred — noted, not silently skipped).
- ✅ **6 Documented** — this runbook + arch.md §7 + hosts.md/api.md + `flow-datasets-lakehouse.md`.
- ▢ **7 Pushed** — pending (code + `k8s/loki/loki-rules-configmap.yaml`).

**MySQL closes the gate once deployed + verified** (hydrate job runs green as a job; DataHub shows the
mysql datasets + lineage; the alert rule loads). The one accepted gap is store-up monitoring (Kuma LAN-DNS
constraint) — a `mysqld-exporter` is the follow-up. Same 7-point gate applies to every store after.

## MySQL (store #1 — loaded; completeness punch-list open)

- **Deploy:** `mysql.data-mesh.svc:3306`, **always-on** (`deployment.apps/mysql`, no ScaledObject), user
  `weyland` / shared dev password. 6 databases pre-created, empty, matching the grid.
- **Targets (grid `MySQL=Y`):** `nhanes`, `big_five`, `who_gho`, `cdc_physical_activity`, `brfss`, `nhis`
  (health). USDA + Open Food Facts are `MySQL=N`; all music is `N`.
- **Mapping:** **dataset → database** (pre-created), **each parquet file → a table** (e.g. the `nhanes` DB
  gets `t_2017_2020_demo_j`, `t_2015_2016_bmx_i`, … one per XPT cycle file; `brfss` gets its per-file tables).
  Table names via `_sql_ident` (non-`[A-Za-z0-9_]` → `_`, digit-leading guard).
- **Write:** `pandas.to_sql` over a `mysql+pymysql://` SQLAlchemy engine per database; **batched**
  (pyarrow `iter_batches(50k)` → pandas → `to_sql(..., if_exists="replace"` on first batch then `"append")`)
  so big tables (brfss ~3M rows) stay memory-bounded. `to_sql` auto-creates the table from the Arrow→pandas schema.
- **Driver:** `SQLAlchemy` + `PyMySQL` (added to the user-code image's requirements).
- **Connection:** `MYSQL_HOST/PORT/USER/PASSWORD` env on the user-code deployment (`k8s/dagster/user-code.yaml`).
- **Asset:** `datasets_health_mysql_load` — materialize it (or run the future hydrate job) after the health
  transform is green.

## TimescaleDB (store #2 — WHO GHO hypertables, 2026-07-01)

- **Target (grid `TimescaleDB=Y`):** `who_gho` only. Last.fm is `Y` in the grid but **skipped** — its silver is
  lifetime user↔artist playcounts with no per-listen timestamps, so it isn't a time-series (only `signup_date`
  is temporal; forcing it in would be square-peg cruft). Recorded in the `timescale_allow` comment.
- **Loader:** `datasets_health_timescaledb_load` (the `timescale_allow={"who_gho": "TimeDim"}` arm of
  `build_store_load_assets`). Each WHO GHO indicator parquet → a **hypertable** in db `timeseries`, named
  `who_gho_<indicator>` (dataset-prefixed — TimescaleDB is one flat db). Time axis: a derived `ts` timestamptz
  = `TimeDim` (the year) → Jan 1; rows with no usable year are dropped (a hypertable's time column must be non-null).
  `to_sql` then `create_hypertable(..., migrate_data => TRUE, if_not_exists => TRUE)`.
- **Connection:** the existing `TIMESCALEDB_*` defaults (`timescaledb.data-mesh.svc:5432`, db `timeseries`,
  `weyland`/dev pw) — no new env. Runs in `weyland_datasets_health_hydrate_job` (same `datasets_health_stores` group).
- **Gate:** Loaded ✅ · Runnable ✅ · Gated ✅ (parquet dep) · Cataloged ✅ (`emit_timescaledb` scans all
  hypertables) · Monitored ✅ (rides the hydrate-failure Loki rule) · Documented ✅ · Pushed ▢.

## MongoDB (store #3 — document store, 2026-07-02)

- **Targets (grid `MongoDB=Y`):** `who_gho` (nested JSON) + `open_food_facts` (doc per product). **Plus aidlc-kb**
  (the methodology corpus — NOT a grid dataset; added because scanning it BY FRONTMATTER is a real consumer
  that the vector RAG (semantic) and Neo4j (relationships) don't serve).
- **Deploy:** always-on `mongo:8` (`mongodb.data-mesh.svc:27017`, `k8s/data-mesh/mongodb.yaml`), user
  `weyland`/dev-pw, **authSource `admin`** (root user lives there — omitting it is the classic auth trap).
- **Loaders:** two paths →
  - `datasets_health_mongodb_load` (the `mongo_allow` arm) — silver parquet → collection per file in db
    `datasets_health` (who_gho_*, open_food_facts). **Memory-safe**: the parquet is **downloaded to a temp
    file** (not `io.fetch`-into-RAM) and read in **20k-row batches** → `insert_many`. The naive whole-file +
    50k-dict-batch approach **OOMKilled** user-code at ~3.9M/4.5M OFF docs (exit 137); temp-file + smaller
    batch fixed it. OFF's silver comes from the streamed asset, so the loader deps on it via `streamed_parquet`.
  - `aidlc_kb_mongo` (in `aidlc_kb.py`, reuses `_read_minio_docs`/`_parse_frontmatter`) — corpus markdown →
    `aidlc_kb.entries`, frontmatter flattened to top-level queryable fields + body. Empty-read guard (won't
    drop the collection on a MinIO failure). Runs in `weyland_aidlc_kb_job`.
- **Prereqs:** `pymongo` (requirements) + `MONGO_*` env on user-code (defaults match, so it works pre-push).
- **Cataloged:** DataHub **native MongoDB source** (recipe scoped to `datasets_health`+`aidlc_kb`, schema
  inference by sampling) — root source, no parquet lineage (same as the MusicBrainz native source).
- **Gate:** Loaded ✅ (4.5M OFF + 8 who_gho + 511 aidlc-kb) · Runnable ✅ · Gated ✅ · Monitored ✅ (`MongodbDown`) ·
  Cataloged ✅ · Documented ✅ · Pushed ▢.

## CockroachDB (store #4 — distributed SQL, 2026-07-02)

- **Targets (grid `CockroachDB=Y`):** `brfss` + `nhis` (US health survey — "geo-partitioned" intent).
  **Single-node lab can't actually geo-partition** (needs a multi-node/region cluster) — this loads the tables
  + demonstrates the store + pg-wire + the built-in Admin UI; geo-partitioning is aspirational (not a data
  mismatch, the data fits).
- **Deploy:** single-node `cockroachdb/cockroach:v24.2.4` **insecure** (`start-single-node --insecure` — no
  TLS/auth, LAN + in-cluster only), always-on (`cockroachdb.data-mesh.svc:26257` SQL, `:8080` UI). Admin UI at
  **`cockroachdb.weyland.lab`** behind Keycloak forward-auth (the insecure UI has no login of its own, so
  forward-auth IS the gate). `k8s/data-mesh/cockroachdb.yaml`.
- **Loader:** `datasets_health_cockroachdb_load` (`cockroach_allow={brfss, nhis}`) — DB per dataset, table per
  file via `to_sql`, memory-safe temp-file read (BRFSS ~3M). **Dialect gotcha:** Cockroach is pg-*wire* but the
  plain SQLAlchemy postgres dialect **AssertionErrors parsing its version string** (`CockroachDB CCL v24…`) →
  use the **`cockroachdb://` dialect** (`sqlalchemy-cockroachdb`), not `postgresql+psycopg2://`.
- **Cataloged:** DataHub native source (platform `cockroachdb`), like the MusicBrainz/Mongo native sources.
- **Gate:** Loaded ✅ · Runnable ✅ · Gated ✅ · Monitored ✅ (`CockroachdbDown`) · Cataloged ✅ · Documented ✅ · Pushed ▢.

## Cassandra (store #9 — wide-column, 2026-07-02)

- **Targets (grid `Cassandra=Y`):** music `uci_year_prediction` + `lastfm` (~17M user↔artist playcounts);
  health `big_five` + `who_gho`. Keyspace per domain (`datasets_music`, `datasets_health`).
- **Deploy:** single-node `cassandra:5.0` **StatefulSet** (headless svc, PVC), **3G heap / 6Gi limit** — the
  heaviest Tier-2 store (a JVM). mother bumped 44→50Gi to fit it (RAM reclaimed by stopping the shelved
  `openclaw` VM — the Proxmox host was near-full, and a *stopped VM* releases its reservation; LXC caps aren't
  reservable). No auth (AllowAllAuthenticator). `k8s/data-mesh/cassandra.yaml`.
- **Loader:** `datasets_{music,health}_cassandra_load` (`cassandra_allow={dataset: partition_col}`) — table per
  file, prepared INSERT + `execute_concurrent`, temp-file streaming. **Query-first:** partition = a natural
  column + synthetic `row_id uuid` clustering (nothing collides).
- **Gotchas:** ① partition keys can't be null/empty (`Key may not be empty` fails the whole batch) → force the
  partition col to `text` + a `__UNKNOWN__` sentinel. ② wrong partition col → falls back to a row_id dump + logs
  the real columns (that's how lastfm's real key `user_id`, not `user`, surfaced). ③ the **headless** svc only
  has DNS when the pod is Ready — loading during a restart → `UnresolvableContactPoints: {}`; wait for `1/1`.
- **Cataloged:** DataHub native `cassandra` source (no auth; profiling table-level but **lastfm excluded** via
  `profile_pattern.deny` — a Cassandra `COUNT` is a full-partition scan). Weekly Sun 04:15 ([../schedules.md](../schedules.md)).
- **Gate:** Loaded ✅ · Runnable ✅ · Always-on ✅ · Monitored ✅ (`CassandraDown`) · Cataloged ✅ · Documented ✅ · Pushed ▢.

## ClickHouse (store #10 — columnar OLAP, 2026-07-02)

- **Targets (grid `ClickHouse=Y`):** music `fma_tracks`, `uci_year_prediction`, `musicbrainz` (HF subset — NOT
  the full mirror), `lp_musiccaps_mc/mtt`, `audioset`; health `usda_fooddata`, `open_food_facts`. Db per domain.
- **Deploy:** single-node `clickhouse/clickhouse-server:24.8`, ns `data-mesh`, always-on. **8Gi limit** (4Gi
  OOM'd the OFF ingest — 211 cols × 4.5M). `/play` web UI at `clickhouse.weyland.lab` (Keycloak forward-auth;
  loader + DataGrip use the in-cluster svc `:8123`/`:9000`). `k8s/data-mesh/clickhouse.yaml`.
- **Loader:** `datasets_{music,health}_clickhouse_load` (`clickhouse_allow`) — **native `s3()` ingest**: ClickHouse
  reads the silver parquet straight from the **lakeFS S3 gateway** (`CREATE TABLE … MergeTree ORDER BY tuple() AS
  SELECT * FROM s3(url, key, secret, 'Parquet')`), schema inferred, columnar-fast (`food_nutrient` 26.8M in
  seconds — the anti-Cassandra). No Python row loop.
- **Gotchas:** ① wide-table ingests are memory-heavy → bump the container (OFF needed 8Gi). ② all-null parquet
  columns break schema inference (`Unsupported Parquet type 'null'`) → the loader sets
  `input_format_parquet_skip_columns_with_unsupported_types_in_schema_inference = 1` (drops the empty column,
  lossless). ③ **DataHub's clickhouse-sqlalchemy CANNOT do no-auth** — it sends an empty password that a
  `no_password` user rejects (516) → `default` was given a password via a `users.d` **Secret** (`replace="replace"`
  to override the base), loader reads `CLICKHOUSE_PASSWORD`. ④ IntelliJ/DataGrip throws `[08000] databaseTerm/
  session_id` → **add** `databaseTerm=schema` in Advanced (don't remove it, don't downgrade the driver). ⑤ DataHub
  recipe: HTTP `:8123`, `password` set, `database_pattern` allow the two dbs (profiling cheap — columnar counts).
- **Cataloged:** DataHub native `clickhouse` source. Weekly Sun 04:30 ([../schedules.md](../schedules.md)).
- **fma_tracks fixed (2026-07-03):** its silver was corrupt (the FMA land read a single-header `tracks.csv` with
  `header=[0,1]`, baking row-0 data into the column names) → the ClickHouse table was junk. Root-caused + fixed
  at the land (`header=0`), re-transformed, and **reloaded clean** (109,727 rows, native s3()).
- **Gate:** Loaded ✅ · Runnable ✅ · Always-on ✅ · Monitored ✅ (`ClickhouseDown`) · Cataloged ✅ · Documented ✅ · Pushed ▢.

## Neo4j (store #11 — GRAPH, B1 2026-07-03)

- **Targets (grid `Neo4j=Y`):** the relationship-shaped MUSIC sets only — `fma_genres` (genre tree), `lastfm`
  (user↔artist plays), `fma_tracks` (track↔artist/album/genre), `audioset` (clip↔labels). musicbrainz → N (flat
  mbid dictionary, no edges); UCI/Big Five dropped (grid said "graph" but the data has no relationships).
- **Deploy:** the existing always-on neo4j (ns `weyland`, +APOC/GDS) — the RAG/AIDLC graph host, now ALSO the
  dataset graph store. Bumped **2G heap / 2G pagecache / 5Gi** for the ~14M-edge lastfm load. Stays MESHED via a
  `neo4j-bolt` DestinationRule (TCP keepalive). `k8s/neo4j.yaml`.
- **Loader:** `datasets_music_neo4j_load` (`neo4j_allow = {dataset: GraphSpec}`). A GraphSpec declares
  `nodes[] + edges[]` from parquet columns; loader creates a uniqueness constraint per key, clean-rebuilds only
  its `clear_labels`, then batches nodes MERGE + edges MATCH…CREATE. Model: [../diagrams/graph-music-model.md](../diagrams/graph-music-model.md).
- **Gotchas:** ① **CREATE not MERGE for edges** — MERGE-rel into a supernode (radiohead ~40k listeners) is
  O(degree) → never finishes; silver has unique pairs so CREATE is safe. ② **key-size guard** — a 120KB garbage
  artist_name blew the RANGE index → keys >1000 chars skipped. ③ **Bolt half-open stall** — one long-lived Bolt
  connection through the Istio sidecar half-closes mid-load → driver hangs forever (both pods idle, no txn); fix
  = the DestinationRule keepalive + per-batch auto-retried `execute_write` (do NOT pull neo4j from the mesh). ④
  **shared labels** — `:Artist`/`:Genre` span datasets → `clear_labels` omits them so a fma_tracks reload can't
  wipe lastfm's PLAYS. ⑤ **multi-value cols** — `dst_list` (audioset human_labels) / `dst_list_key` (fma_tracks
  track_genres list-of-dicts → genre_id, int-coerced to match the tree).
- **Load ONE dataset** (without re-clearing lastfm's 13.85M): call `loaders._load_dataset_to_neo4j(...)` directly
  in the dagster-user-code pod — materializing the whole asset re-does every dataset.
- **Cataloged:** N/A — DataHub has no native source for an arbitrary node/edge model. Browse via Neo4j Browser /
  NeoDash; importable favorites + dashboard in [../query/](../query/neo4j.md).
- **Gate:** Loaded ✅ · Runnable ✅ · Always-on ✅ · Monitored ✅ (neo4j liveness) · Cataloged N/A · Documented ✅ · Pushed ▢.

## Qdrant + Weaviate (stores #12/#13 — VECTOR, B1 2026-07-03)

- **Targets (grid `Qdrant=Y` = `Weaviate=Y` — identical sets):** audio-feature + text sets — fma_features,
  fma_echonest, uci, spotify_tracks, gtzan, lp_musiccaps_mc/mtt, audioset (music) + big_five (health). fma_tracks
  DROPPED (metadata not features — sound-sim is fma_features/echonest via track_id); open_food_facts → B78 (4.5M capped).
- **Deploy:** the existing always-on Qdrant + Weaviate (the RAG backends, ns `weyland`). No new deploy.
- **Loader:** `datasets_{d}_qdrant_load` + `datasets_{d}_weaviate_load` (`vector_allow = {dataset: vector_spec}`).
  A **shared `_build_vectors`** builds each dataset's vectors ONCE — numeric specs assemble feature cols
  **z-scored** (raw scales differ wildly → cosine meaningless otherwise); text specs concat cols + embed with
  **bge-small** (384-d, the RAG's model) — then each backend's arm upserts (Qdrant collection / Weaviate class
  per dataset; dims differ → separate spaces). SEPARATE assets (not one) → independent rerun; the double
  vectorize is negligible at these sizes. Env (`QDRANT_*`/`WEAVIATE_*`) already on the pod.
- **gtzan land fix (prereq):** its silver was `(label, genre)` only — the old land skipped the audio column.
  Rewrote it to **decode the clips + extract librosa features** (chroma/mfcc/spectral/zcr/tempo mean+var, ~53-d).
  Gotcha: HF `datasets` Audio decode now demands the heavy `torchcodec`/torch → use `Audio(decode=False)` +
  soundfile instead. (librosa + soundfile added to requirements.)
- **Gotchas:** ① point ids are sequential ints (Qdrant) / auto-UUIDs (Weaviate) — the real id is payload
  `row_id`. ② BYO vectors (Weaviate `Vectorizer.none()`) — search by vector/object, not raw text; embed text
  queries with bge yourself. ③ payloads stringified (JSON/GraphQL-safe). ④ genre-NN on the tiny 443-clip gtzan is
  fuzzy (disco↔hiphop↔reggae rhythmic confusion — normal for feature-NN, not a bug).
- **Cataloged:** ✅ existing DataHub custom-emit (`emit_qdrant`/`emit_weaviate`). Queries: [../query/qdrant.md](../query/qdrant.md) · [../query/weaviate.md](../query/weaviate.md).
- **Gate:** Loaded ✅ (9 collections/classes each) · Runnable ✅ · Always-on ✅ · Monitored ✅ · Cataloged ✅ · Documented ✅ · Pushed ▢.

## Store roadmap (the grid's Tier-2 targets)

| Store | Deployed? | Loader | Grid targets (datasets) |
|---|---|---|---|
| **MySQL** | ✅ always-on | ✅ **done** | health: nhanes, big_five, who_gho, cdc_physical_activity, brfss, nhis |
| TimescaleDB | ✅ | ✅ **done** | who_gho (country/year → 8 hypertables). Last.fm **skipped** — its silver is lifetime playcounts, no per-listen timestamps (not a real time-series) |
| **Neo4j** | ✅ always-on | ✅ **done** | GRAPH (music): fma_genres tree · lastfm ~13.85M PLAYS · fma_tracks (BY/ON/IN_GENRE) · audioset (HAS_LABEL). musicbrainz/uci/big_five → N (flat, no edges) |
| OpenSearch | ✅ (RAG) | ▢ | search: fma_tracks, uci, musicbrainz, lp_musiccaps_*, audioset, usda, open_food_facts |
| **Qdrant + Weaviate** | ✅ always-on | ✅ **done** | VECTOR (9 each, one build → both): fma_features/echonest/uci/spotify/gtzan (z-scored audio features) · lp_musiccaps×2/audioset (bge text) · big_five (OCEAN). fma_tracks dropped · OFF → B78 |
| ClickHouse | ✅ always-on | ✅ **done** | music: fma_tracks, uci, musicbrainz-subset, lp_musiccaps, audioset · health: usda, open_food_facts (native s3() ingest) |
| Cassandra | ✅ always-on | ✅ **done** | music: uci, lastfm (~17M, by user_id) · health: big_five, who_gho |
| CockroachDB | ✅ always-on | ✅ **done** | brfss (6 tables, ~3M rows) + nhis — db per dataset, pg-wire |
| MongoDB | ✅ always-on | ✅ **done** | who_gho (8 collections) + open_food_facts (4.5M docs) + aidlc-kb (511 frontmatter docs) |
| Feast | ▢ deploy first | ▢ | feature store (audio/health features) |

Each new store = a `<store>_allow` field on `DomainConfig` + a writer arm in `loaders.py` + (if not
deployed) standing up the store first. Full per-dataset targets in [data-pipeline-flows.md](../data-pipeline-flows.md).

## Deploy

The loader is in the user-code image **and** adds Python deps (`SQLAlchemy`, `PyMySQL`) — so rebuild the
image (the `:local` procedure in [validation/test-commands.md](../validation/test-commands.md)) and **push
`k8s/dagster/user-code.yaml`** (the new `MYSQL_*` env) so Argo rolls the deployment.

```bash
# verify load (in-pod) — table counts per MySQL database after running datasets_health_mysql_load
kubectl -n data-mesh exec deploy/mysql -- sh -c 'mysql -uweyland -pweyland_dev_password -e "SELECT table_schema db, COUNT(*) tables FROM information_schema.tables WHERE table_schema IN (\"nhanes\",\"big_five\",\"who_gho\",\"cdc_physical_activity\",\"brfss\",\"nhis\") GROUP BY table_schema;"' 2>/dev/null
```

## Status (2026-07-01)

- ✅ **MySQL — LOADED + verified** (completeness punch-list open: job, DataHub lineage, monitoring — see the
  completeness gate above). `datasets_health_mysql_load` hydrated all 6 DBs: **32 tables** (nhanes 13,
  who_gho 8, brfss 6, nhis 3, cdc 1, big_five 1). Proved the full vertical: land → silver → quality checks →
  hydration. Two fixes surfaced and were made at the right layers: **big_five's TSV** (fixed at *land* —
  `data.csv` is tab-separated → convert to comma-CSV; flowed through every format + store for free) and the
  **`to_sql` insert method** (`method="multi"` compiles chunksize×columns bind params → hung on big_five's
  57 columns → switched to the default `executemany`). `RefreshConfig.force` was wired into big_five for a
  wipe-free re-land.
- ▢ Remaining stores per the roadmap table. Deploy-gated ones (ClickHouse/Cassandra/CockroachDB/Mongo/Feast)
  need standing up before their loader.
- ▢ Quality gate wiring (B77 native checks already gate via the parquet dep; GE → DataHub Assertions = later).
