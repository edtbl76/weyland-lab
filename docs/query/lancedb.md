# LanceDB — query cookbook (embedded, Lance-native vectors)

LanceDB is an **embedded** vector DB — a library, not a server (like DuckDB/SQLite for vectors). There's no
port, no JDBC, no wire protocol: you query it **in-process** by connecting to its storage (our tables live on
the lakeFS S3 gateway). Same feature vectors as [Qdrant](qdrant.md)/[Weaviate](weaviate.md), different
architecture (serverless, object-storage-native, Lance columnar format). See
[../runbooks/datasets-hydration.md](../runbooks/datasets-hydration.md).

**Tables** (one per dataset, per-domain db `s3://<repo>/main/lancedb`): music — `audioset`, `fma_echonest`,
`fma_features`, `gtzan`, `lp_musiccaps_mc`, `lp_musiccaps_mtt`, `spotify_tracks`, `uci_year_prediction`; health —
`big_five`. Each row = `vector` (FixedSizeList<float>) + `row_id` + payload columns.

**Connect** — anywhere with `lancedb` + the lakeFS creds (the dagster pod has both). The loader's helper opens
the right db per domain:
```python
from weyland_pipeline.assets.datasets_lib.loaders import _lancedb_connect
from weyland_pipeline.assets.datasets_music_transform import MUSIC_CFG
db = _lancedb_connect(MUSIC_CFG)         # s3://music/main/lancedb, on the lakeFS gateway
[t.name for t in [db]] ; db.list_tables()
```
Convenience wrapper: **`scripts/lancedb_query.py`** (below) —
`kubectl -n weyland exec -i deploy/dagster-user-code -- python - < scripts/lancedb_query.py music gtzan`.

## Similarity — the point of the store
```python
t = db.open_table("gtzan")
v = t.to_pandas()["vector"][0]                                   # a known row's vector
t.search(v).limit(10).select(["row_id", "genre"]).to_pandas()   # 10 nearest (ANN if indexed, else exact)
```
**Text sets** (lp_musiccaps / audioset) — embed the query with bge-small first (the loader's model), then search:
```python
from sentence_transformers import SentenceTransformer
qv = SentenceTransformer("BAAI/bge-small-en-v1.5").encode("mellow acoustic guitar", normalize_embeddings=True).tolist()
db.open_table("lp_musiccaps_mc").search(qv).limit(10).to_pandas()
```

## Filtered search (SQL `where`)
```python
t.search(v).where("genre = 'metal'").limit(10).to_pandas()      # nearest within a genre
t.search(v).where("genre != 'disco'").limit(10).to_pandas()
```

## Plain scan (no vector)
```python
db.open_table("big_five").to_pandas().head()                    # whole table → pandas
db.open_table("big_five").count_rows()
```

## LanceDB-isms
- **Embedded — no server/port/JDBC.** Query in-process (Python `lancedb`); there's no dashboard/Console like
  Qdrant/Weaviate. See the runbook for the IntelliJ-browse option via DuckDB.
- **ANN index only when ≥2000 rows** (the loader builds `create_index(metric="cosine")`); smaller tables do
  exact search transparently — results are the same, just slower at scale.
- **Object-storage-native** — tables are Lance datasets on the lakeFS S3 gateway; LanceDB streams from storage,
  so it holds datasets larger than RAM (the reason OFF → LanceDB is the natural B78 home, where the server DBs
  can't fit it).
- Cataloged in DataHub via the `emit_lancedb` custom emitter (platform `lancedb`) — no native source (it's not
  a server DB).
