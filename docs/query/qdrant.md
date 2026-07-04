# Qdrant — query cookbook (dataset vectors)

Qdrant holds one **collection per dataset** (cosine), built by the `datasets_lib` vector loader from silver.
Numeric sets are z-scored feature vectors; text sets are bge-small (384-dim) embeddings. Payload carries a few
filterable columns + `row_id` (the original id). See [../diagrams/graph-music-model.md] sibling — vectors are
the *feature* slice of the catalog (graph is the *relationship* slice).

**Connect** (in-cluster svc `qdrant.weyland.svc:6333`; for local Python/dashboard, port-forward the svc):
```python
from qdrant_client import QdrantClient
qc = QdrantClient(host="qdrant.weyland.svc.cluster.local", port=6333)   # or localhost via port-forward
```
Web dashboard: `http://<qdrant>:6333/dashboard` (browse collections + points).

**Collections** (per dataset):
`datasets_music_fma_features` (518d) · `datasets_music_fma_echonest` (~244d) · `datasets_music_uci_year_prediction`
(90d) · `datasets_music_spotify_tracks` (11d) · `datasets_music_gtzan` (~53d) · `datasets_music_lp_musiccaps_mc`
(384d) · `datasets_music_lp_musiccaps_mtt` (384d) · `datasets_music_audioset` (384d) · `datasets_health_big_five` (50d).

## Explore
```python
[c.name for c in qc.get_collections().collections]
qc.count("datasets_music_fma_features").count                 # points in a collection
qc.retrieve("datasets_music_fma_features", ids=[0, 1], with_payload=True)
```

## Similarity — the point of the store
**"Songs that sound like this one"** — recommend by an existing point (numeric feature sets):
```python
qc.query_points("datasets_music_fma_features", query=42, limit=10, with_payload=True)   # nearest to point 42
```
Or by a raw vector you already have:
```python
v = qc.retrieve("datasets_music_gtzan", ids=[0], with_vectors=True)[0].vector
qc.query_points("datasets_music_gtzan", query=v, limit=10, with_payload=True)
```

**Text sets** (lp_musiccaps / audioset) — embed a query with bge-small first (same model the loader used):
```python
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("BAAI/bge-small-en-v1.5")
qv = m.encode("upbeat acoustic guitar with vocals", normalize_embeddings=True).tolist()
qc.query_points("datasets_music_lp_musiccaps_mc", query=qv, limit=10, with_payload=True)
```

**Filtered** (payload) — nearest within a genre:
```python
from qdrant_client.models import Filter, FieldCondition, MatchValue
qc.query_points("datasets_music_spotify_tracks", query=42, limit=10,
                query_filter=Filter(must=[FieldCondition(key="track_genre", match=MatchValue(value="metal"))]))
```

## Qdrant-isms
- **Point ids are sequential ints** (0..N-1); the dataset's real id is `payload.row_id`. Payload values are
  stringified (JSON-safe) — filter on strings.
- **No text vectorizer** — these are BYO-vector collections, so you search by a **vector or an existing point**,
  not by raw text. For text sets, embed the query with bge-small yourself (as above).
- Same vectors also live in **Weaviate** ([weaviate.md](weaviate.md)) — Qdrant and Weaviate hold identical
  dataset vectors, two backends for comparison.
- Numeric vectors are **z-scored** at load — cosine similarity is over the normalized feature space.
