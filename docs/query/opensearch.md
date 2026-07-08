# OpenSearch — query cookbook

OpenSearch is the **lexical / BM25** search backend of the mesh — the sparse complement to the dense/vector
stores (pgvector · Qdrant · Weaviate · Neo4j). Single-node OpenSearch 3.x in ns `opensearch`, **security plugin
OFF** → plain HTTP, **no auth, no creds**. Two flavours of index live here: the **RAG corpus** index
`weyland_chunks` (BM25 over document chunks, written by the Dagster `opensearch_write` asset), and a set of
**doc-per-row dataset indices** (index per silver parquet file, written by the `datasets_*_opensearch_load`
assets). Everything is REST — you query it with `curl`.

**Connect:** the 9200 REST port is **not** exposed on the LAN (only the Dashboards UI is). Two ways in:
- **Dashboards Dev Tools** — `opensearch.weyland.lab` → *Dev Tools* console (Keycloak forward-auth gated; log in
  with your lab SSO). Paste the `METHOD /path` + JSON body, hit run. Best for exploring.
- **curl**, either port-forward the svc `opensearch-cluster-master` `9200` and hit `127.0.0.1:9200`, or in-pod:
  `kubectl -n opensearch exec opensearch-cluster-master-0 -- curl -s localhost:9200/...`

In-cluster clients (Dagster, tool-server) use `http://opensearch-cluster-master.opensearch.svc.cluster.local:9200`.

### What's indexed

| Index | Source | Docs | Key fields |
|---|---|---|---|
| `weyland_chunks` | RAG corpus chunks (`opensearch_write`) | one per chunk | `content` (analyzed→BM25), `source_path`, `source_name`, `chunk_index`, `chunk_title`, `domain` |
| dataset indices | silver parquet, doc-per-row (`datasets_*_opensearch_load`) | one per row | the parquet columns of that dataset |

Dataset indices (from `opensearch_allow`): **music** — `spotify_tracks`, `fma_tracks`, `fma_echonest`,
`fma_features`, `uci_year_prediction`, `gtzan`, `lp_musiccaps_mc`, `lp_musiccaps_mtt`, `audioset`;
**health** — `big_five`, `open_food_facts`. Index name = sanitized parquet file name (lowercase, non-`[a-z0-9_]`→`_`);
a multi-file dataset yields `<dataset>_<filename>` indices, so **list first** rather than guessing.

### Explore
```bash
# every index + doc count + size (start here — authoritative index names)
curl -s "localhost:9200/_cat/indices?v&s=index"

# the RAG index's mapping (field types)
curl -s "localhost:9200/weyland_chunks/_mapping?pretty"

# one sample doc from an index, to see its real columns
curl -s "localhost:9200/weyland_chunks/_search?size=1&pretty"
```

### RAG corpus — `weyland_chunks` (the BM25 lexical backend)
```bash
# BM25 keyword search over chunk text — ranked by relevance (this is what the tool-server calls)
curl -s "localhost:9200/weyland_chunks/_search?pretty" -H 'Content-Type: application/json' -d '{
  "size": 5,
  "query": { "match": { "content": "vector database retrieval" } },
  "_source": ["source_name", "chunk_title", "chunk_index"]
}'

# phrase match — terms must be adjacent (tighter than match)
curl -s "localhost:9200/weyland_chunks/_search?pretty" -H 'Content-Type: application/json' -d '{
  "query": { "match_phrase": { "content": "feature store" } },
  "_source": ["source_path", "chunk_title"]
}'

# bool query: must-match text, filter to one domain, exclude the aidlc-kb corpus
curl -s "localhost:9200/weyland_chunks/_search?pretty" -H 'Content-Type: application/json' -d '{
  "query": { "bool": {
    "must":     [ { "match": { "content": "istio mesh" } } ],
    "must_not": [ { "term":  { "domain": "aidlc-kb" } } ]
  } }
}'

# aggregation: how many chunks per source document (top 20 fattest docs)
curl -s "localhost:9200/weyland_chunks/_search?pretty" -H 'Content-Type: application/json' -d '{
  "size": 0,
  "aggs": { "by_doc": { "terms": { "field": "source_name", "size": 20 } } }
}'

# aggregation: chunk count per domain (keyword field)
curl -s "localhost:9200/weyland_chunks/_search?pretty" -H 'Content-Type: application/json' -d '{
  "size": 0,
  "aggs": { "by_domain": { "terms": { "field": "domain" } } }
}'
```

### Dataset indices — doc-per-row full-text over the silver parquet
```bash
# free-text search across all fields of a dataset (multi_match over every text field)
curl -s "localhost:9200/spotify_tracks/_search?pretty" -H 'Content-Type: application/json' -d '{
  "query": { "query_string": { "query": "acoustic" } }, "size": 5
}'

# open_food_facts: nutrition-grade histogram (keyword sub-field auto-created by dynamic mapping)
curl -s "localhost:9200/open_food_facts/_search?pretty" -H 'Content-Type: application/json' -d '{
  "size": 0,
  "aggs": { "grades": { "terms": { "field": "nutrition_grade_fr.keyword", "size": 10 } } }
}'
```

### Notes
- **No auth.** The security plugin is disabled cluster-wide, so 9200 takes plain HTTP with no user/password.
  Access is gated only at the *Dashboards* ingress (Keycloak forward-auth); the REST API itself is open on-cluster.
- **`text` vs `keyword`.** `content` / `chunk_title` are `text` → analyzed for BM25 (use `match`/`match_phrase`).
  `source_path` / `source_name` / `domain` are `keyword` → exact (use `term`/`terms` and `terms` aggs). Dataset
  indices are dynamically mapped, so string columns get both a `text` field and a `<field>.keyword` sub-field —
  aggregate on `.keyword`.
- **List, don't guess.** Dataset index names derive from parquet file names (`_sql_ident`: lowercase,
  non-alphanumeric→`_`), and multi-file datasets fan out to `<dataset>_<file>` indices. Run `_cat/indices?v` to
  get the real names before querying.
- **Idempotent loads.** RAG writes delete-then-reindex per `source_path` and prune orphans (protecting the
  `domain: aidlc-kb` corpus); dataset loads drop + recreate each index per run. Doc counts move as the pipeline reruns.
- **Add `?pretty`** for readable JSON, `size:0` when you only want aggregations, and `_source` to trim returned fields.

**See also:** [[clickhouse]] (same silver parquet, analytics/SQL) · [[cassandra]] (partition-keyed KV) ·
[[qdrant]] / [[weaviate]] (dense vectors over the same `weyland_chunks` corpus) · runbook `datasets-hydration.md`.
