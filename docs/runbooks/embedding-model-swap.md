# Runbook — Swapping the RAG embedding model (dimension migration)

How to change the model behind the RAG (e.g. `bge-small` 384 → `bge-base` 768, done in **B74** 2026-07-28). This is a
**coordinated migration** — get one piece wrong and the RAG silently half-breaks. Written the hard way; every gotcha
below cost real time.

## The result that justified it (B74)

`bge-small` (384) → `bge-base` (768) + the `embed_text` topic-prefix. Golden set, whole corpus, **every metric up, no
trade**:

| metric | conceptual (small→base) | lexical (small→base) |
|---|---|---|
| context_relevancy | 0.514 → **0.826** | 0.736 → **0.819** |
| faithfulness | 0.660 → 0.814 | 0.780 → 0.854 |
| answer_relevancy | 0.644 → 0.856 | 0.832 → 0.873 |

The conceptual/lexical gap **closed** (bge-small was lopsided; bge-base is even). No hybrid, no bge-large — the cheaper
rung sufficed. (Residual: Q4 "silent sorting" still misses affinity-mapping — a lone surface-token outlier.)

## ⚠️ There are FIVE embedding surfaces — miss one and part of the RAG silently breaks

This is the single biggest trap. Retrieval works only if **every surface agrees on the model + dimension** — index-side
AND both query-side services. The weyland-agent one is the easiest to forget (it embeds queries in-process, separately
from the tool-server) and its miss = a broken agentic RAG, exactly like a wrong-dim index:

| Path | Embedder | Where | Change |
|---|---|---|---|
| **KB** (`aidlc-kb/`) | Dagster `SentenceTransformerResource` (CPU, mother) | `weyland_pipeline/resources/sentence_transformer.py` (`model_name`) | edit + rebuild user-code image |
| **docs/code** | **rogueone GPU service** `rag-embed` (`:8900`) | `services/rag-embed/rag-embed.service` (`EMBED_MODEL` env) | flip env + `systemctl restart` (no rebuild — model auto-downloads) |
| **Query — tool-server** | in-process `HuggingFaceEmbedding` | `weyland-tool-server/main.py` (`MODEL_NAME`) + its Dockerfile bake | edit + rebuild tool-server image |
| **Query — weyland-agent** (B70 agentic RAG) | in-process `HuggingFaceEmbedding` | `weyland-agent/retrievers.py` (`MODEL_NAME`) + its Dockerfile bake | edit + rebuild weyland-agent image (**not** in `build-push-images.sh` — build it manually) |
| *(the 5 `rag-index` consumers)* | **none — they only WRITE the pre-computed vector** | `services/rag-index/` | no model change; just need the target collections at the new dim |

The docs/code path is the sneaky one: `rag_stream_produce` (Dagster) chunks the docs, POSTs the text to the **rogueone
`rag-embed` GPU service**, gets vectors back, and publishes them — so the Dagster `SentenceTransformerResource` change
does **not** touch docs/code. Query + KB + docs/code must all be the same model, or query-vs-index dims disagree.

## The docs/code write path (streaming — NOT the old direct assets)

`source_document` (git-clone `edtbl76/weyland-lab`) → `rag_stream_produce` (chunk + embed via rag-embed) → Redpanda
topic **`rag.chunks`** → **5 always-on `rag-index-*` consumers** → the backends:

- `rag-index-pgvector`, `rag-index-neo4j` — namespace **`weyland`**
- `rag-index-qdrant`, `rag-index-weaviate`, `rag-index-opensearch` — namespace **`data-mesh`**
- Redpanda: `redpanda.data-mesh.svc.cluster.local:9092`

(The old `chunks → embeddings → *_write` assets are **retired** — don't look for them.)

## Dimension migration (384 → 768), per store

| Store | What | Note |
|---|---|---|
| **pgvector** | `TRUNCATE rag_chunks; ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(768);` then **REINDEX** | the ALTER rebuilds the ivfflat index on **empty** data → poor recall → **must REINDEX after re-populating** |
| **qdrant** | delete the `weyland_chunks` collection (recreated at `DIMS` by the next produce) | `DIMS` in `qdrant_write.py` |
| **weaviate** | delete the `WeylandChunk` class | `Vectorizer.none()` infers dim from the first insert — nothing to set |
| **neo4j** | nothing | stores embeddings as a list property, **no dim check** — happily writes mixed dims (a footgun; see scars) |

## Ordered procedure

1. **Code:** bump `model_name` (Dagster resource), `MODEL_NAME` (tool-server), `DIMS` (qdrant_write), both Dockerfile
   model bakes, and `EMBED_MODEL` in `rag-embed.service`.
2. **rogueone rag-embed → new model FIRST** (systemd drop-in `Environment=EMBED_MODEL=…` + `daemon-reload` + `restart`),
   then `curl :8900/embed` and assert the returned vector length is the new dim. **Do this before producing anything.**
3. **Build + push** the user-code + tool-server images (`TAG=vN scripts/build-push-images.sh`), bump the 3 manifests
   (`dagster/user-code.yaml`, `dagster/dbt-docs.yaml`, `weyland-tool-server.yaml`) → push → Argo. Confirm both deploys
   read `:vN` before re-embedding, or the ingest recreates collections at the **old** dim.
4. **Re-dim the stores** (table above).
5. **Re-embed KB:** force its gate — `UPDATE rag_documents SET content_hash='FORCE' WHERE source_path LIKE 'aidlc-kb/%'`
   — then Dagster `weyland_aidlc_kb_job`.
6. **Re-embed docs/code (streaming):** clear the producer's manifest — `DELETE FROM rag_manifest WHERE source_path NOT
   LIKE 'aidlc-kb/%'` — then trigger `weyland_ingestion_job` (runs `rag_stream_produce`). The consumers write.
7. **REINDEX** pgvector, verify `SELECT count(DISTINCT document_id) FROM rag_chunks` ≈ full corpus, then run the golden
   eval (`/evals/run` → `/evals/score` → the conceptual/lexical split query — see eval-harness.md).

## Scars (the mistakes that cost hours — don't repeat)

- **`rag_stream_produce` gates on `rag_manifest`, NOT `rag_documents.content_hash`.** Forcing `rag_documents` re-embeds
  the KB but does **nothing** for docs/code. Clear `rag_manifest` (non-KB rows) to force a re-produce.
- **Publish-then-commit gap:** `rag_stream_produce` commits `rag_manifest` after *publishing*, before the consumers
  write. If a consumer write fails, the manifest still says "done" → the producer never re-emits. The producer thinks
  it succeeded while the data never landed.
- **Order poisons the topic:** producing 384-dim vectors (rag-embed still on the old model) into `rag.chunks`, then
  ALTERing the pgvector column to 768, leaves **stale 384 messages** that crash-loop `rag-index-pgvector`
  (`psycopg2 DataException: expected 768 dimensions, not 384`). qdrant/weaviate crash the same way; **neo4j silently
  writes them** (no dim check). Fix rag-embed **before** any produce, or you'll be cleaning poison.
- **Recovery from a poisoned topic:** `rpk topic delete rag.chunks && rpk topic create rag.chunks -p 3` (via a redpanda
  pod exec) → clear `rag_manifest` → `rollout restart` all 5 consumers → re-produce. Idempotent keyed upserts make the
  replay safe.
- **ivfflat built empty = bad recall.** The `ALTER … TYPE vector(768)` rebuilds `rag_chunks_embedding_idx` on an empty
  table; centroids are garbage until you `REINDEX INDEX rag_chunks_embedding_idx` **after** the corpus is loaded.
- **The datasets pipeline has its OWN embedder** (`datasets_lib/loaders.py` `_embedder()`, env `EMBED_MODEL`, separate
  collections) — a model swap is RAG/KB-scoped and does **not** touch the 9 datasets unless you change that too.

Related: [runbooks/eval-harness.md](eval-harness.md) (the golden set), [runbooks/coding-agents.md](coding-agents.md),
[[eval-golden-set-b96]].
