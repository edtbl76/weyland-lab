# Weaviate — query cookbook (dataset vectors)

Weaviate holds one **class per dataset** (v4 client, BYO vectors / `Vectorizer.none()`), the *same* vectors as
[Qdrant](qdrant.md) — two backends for the identical grid sets. Built by the `datasets_lib` vector loader from
silver: numeric sets = z-scored feature vectors, text sets = bge-small (384-dim).

**Connect** (v4, in-cluster; port-forward http 8080 + grpc 50051 for local):
```python
import weaviate
wc = weaviate.connect_to_custom(
    http_host="weaviate.weyland.svc.cluster.local", http_port=8080, http_secure=False,
    grpc_host="weaviate.weyland.svc.cluster.local", grpc_port=50051, grpc_secure=False)
```

**Classes** (CamelCase per dataset): `DatasetsMusicFmaFeatures` · `DatasetsMusicFmaEchonest` ·
`DatasetsMusicUciYearPrediction` · `DatasetsMusicSpotifyTracks` · `DatasetsMusicGtzan` ·
`DatasetsMusicLpMusiccapsMc` · `DatasetsMusicLpMusiccapsMtt` · `DatasetsMusicAudioset` · `DatasetsHealthBigFive`.

## Explore
```python
[c.name for c in wc.collections.list_all().values()]
col = wc.collections.get("DatasetsMusicFmaFeatures")
col.aggregate.over_all(total_count=True).total_count
for o in col.iterator(return_properties=["row_id"]):
    print(o.uuid, o.properties); break
```

## Similarity
**Recommend by an existing object** (feature sets) — nearest to a known object:
```python
col = wc.collections.get("DatasetsMusicGtzan")
some = next(col.iterator(include_vector=True))
res = col.query.near_object(some.uuid, limit=10, return_properties=["row_id", "genre"])
for o in res.objects: print(o.properties)
```

**Text sets** — embed the query with bge-small, then `near_vector`:
```python
from sentence_transformers import SentenceTransformer
qv = SentenceTransformer("BAAI/bge-small-en-v1.5").encode("mellow lo-fi beat", normalize_embeddings=True).tolist()
col = wc.collections.get("DatasetsMusicLpMusiccapsMc")
res = col.query.near_vector(qv, limit=10, return_properties=["row_id", "caption_summary"])
```

**Filtered** — nearest within a property value:
```python
from weaviate.classes.query import Filter
col = wc.collections.get("DatasetsMusicSpotifyTracks")
some = next(col.iterator(include_vector=True))
res = col.query.near_object(some.uuid, limit=10,
                            filters=Filter.by_property("track_genre").equal("metal"))
```

Always `wc.close()` when done (v4 holds a gRPC channel).

## Weaviate-isms
- **BYO vectors** (`Vectorizer.none()`) — no server-side text vectorizer, so search by **vector or object**,
  not raw text. Embed text queries with bge-small yourself (the loader's model).
- Objects get **auto-UUIDs**; the dataset's real id is property `row_id`. All properties are `TEXT` (payloads
  are stringified at load).
- Same vectors as [Qdrant](qdrant.md); the RAG's own `WeylandChunk`/`WeylandDocument` classes are separate.
