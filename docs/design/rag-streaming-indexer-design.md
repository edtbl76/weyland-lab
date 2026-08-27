# RAG Streaming Indexer — Design (B-RAG-STREAM)

**Status**: Proposed · **Date**: 2026-07-14 · **Phase**: Construction / Application Design
**Owner**: Engineering · **Supersedes**: the in-process `weyland_ingestion_job` RAG asset chain

---

## 1. Problem

The RAG index is currently built by an in-process Dagster asset chain:

```
source_document ─▶ chunks ─▶ embeddings (list[dict]: chunk text + 384-dim vector)
                                 ├─▶ qdrant_write
                                 ├─▶ weaviate_write
                                 ├─▶ pgvector_write
                                 ├─▶ neo4j_write
                                 └─▶ opensearch_write
```

`embeddings` is one `list[dict]` holding **every chunk's text and its vector**. Dagster's default IO
manager pickles it whole and **re-loads it into RAM once per writer** — the embed cost is paid once but the
full payload is materialized and re-read five times, and both the model and the vector set live inside the
orchestrator's process.

**Root cause (measured).** The `datahub_catalog_emit_job` and full-`definitions` import both peak at ~1.1–1.24 GB;
they are not the hog. The `dagster-user-code` pod (limit 12 Gi, request 4 Gi) OOMKills — restart count 4 — during
the **ingestion** run: the sentence-transformer plus the whole-in-memory `embeddings` set, re-loaded across five
writers, in a pod also running the gRPC code server. With `DefaultRunLauncher` + `QueuedRunCoordinator`
(`max_concurrent_runs: 1`), a heavy/hung ingestion run OOMs the shared pod **and** never releases the single
concurrency slot — so the cheap emit run is starved behind it. Both jobs "hang every night" from one cause.

This is a **category error**: Dagster is a control plane (trigger, schedule, lineage, retry, observe). Here it is
being used as the data plane — bulk chunks and vectors flow *through* the orchestrator. Batching the payload shrinks
the symptom; it does not remove the cause.

## 2. Invariants (acceptance criteria)

Any correct design must satisfy all six. These are the acceptance criteria for this unit.

| # | Invariant | Current design |
|---|---|---|
| I1 | **Embed exactly once** — never per-store | FAIL (embedded once, re-read 5×; model in orchestrator) |
| I2 | **Stream, never materialize whole** — peak memory bounded by batch, not corpus | FAIL |
| I3 | **Reference boundary at the orchestrator** — payload never crosses Dagster | FAIL |
| I4 | **Per-store failure isolation + independent retry** | FAIL (one writer failure fails the run) |
| I5 | **Whole-state orphan prune** — deletes what is no longer collected | PASS (per-writer prune) |
| I6 | **Warm model** — amortize model load | FAIL (loads per run) |

## 3. Target Architecture

A streaming indexer: Dagster orchestrates, a warm GPU service embeds, Redpanda fans out, five independent
consumers own their stores. Prune is expressed as tombstone records, not a whole-state pass.

```
 changed files
      │
      ▼
 ┌──────────────────────────┐   manifest (paths + hashes + current-path set); NO payload
 │ Dagster (control plane)  │────────────────────────────────────────────────┐
 │  sensor: hash_check      │                                                 │
 │  K8sRunLauncher (opt.)   │                                                 ▼
 └──────────────────────────┘                                        ┌─────────────────┐
                                                                     │ Producer (worker)│
                                                                     │  chunk (Llama-   │
                                                                     │  Index splitter) │
                                    embed batch (HTTP/gRPC)          │  → embed → publish│
                    ┌────────────────────────────────────────────────┤  streaming, 1    │
                    ▼                                                 │  batch in memory │
        ┌───────────────────────┐                                    └─────────────────┘
        │ Embedding service     │                                             │
        │ rogueone GPU (warm)   │  vectors                                    │ upsert + tombstone records
        │ bge-small-en-v1.5     │─────────────────────────────────────────▶  │ keyed by source_path
        └───────────────────────┘                                            ▼
                                                          ┌──────────────────────────────────┐
                                                          │ Redpanda topic  rag.chunks        │
                                                          │  Avro (schema registry)           │
                                                          │  partition key = source_path      │
                                                          └──────────────────────────────────┘
                                                             │    │    │    │    │
                          ┌──────────────────────────────────┘    │    │    │    └───────────────────────┐
                          ▼                     ▼                  ▼    ▼    ▼                            ▼
                   ┌────────────┐        ┌────────────┐     ┌────────────┐  ┌────────────┐        ┌────────────┐
                   │ qdrant     │        │ weaviate   │     │ pgvector   │  │ neo4j      │        │ opensearch │
                   │ consumer   │        │ consumer   │     │ consumer   │  │ consumer   │        │ consumer   │
                   │ (group)    │        │ (group)    │     │ (group)    │  │ (graph)    │        │ (lexical)  │
                   └────────────┘        └────────────┘     └────────────┘  └────────────┘        └────────────┘
```

### 3.1 Control plane — Dagster (under K8sRunLauncher, optional)

- A sensor runs the existing `hash_check` logic against the collected sources and produces a **manifest**:
  the changed/added `source_path`s (+ content hashes + `kind`) and the **full current-path set** for this run.
- Dagster triggers the producer and records the run + lineage. It carries **only the manifest** — never a chunk
  or a vector. This satisfies **I3**.
- `K8sRunLauncher` is **demoted to optional insurance**. It is no longer load-bearing for this job (the data
  plane has left Dagster). Keep it only to isolate the *other* heavy in-process runs still in the pod — the
  Tier-2 hydrates (Cassandra 515k, Cockroach ~3M, Mongo 4.5M) and dbt — from OOMing/starving the shared code
  server. Decision recorded in §8.

### 3.2 Embedding service — rogueone (warm, GPU)

- Standing service holding `bge-small-en-v1.5` resident on the RTX 5000 Ada (alongside Ollama).
- Contract: `POST /embed { texts: [str] } → { vectors: [[float]] }`, batched. Model + CUDA context load once at
  startup; every request is warm. Satisfies **I6**.
- Footprint: ~1–1.5 GB VRAM (CUDA context dominates; weights ~66–130 MB), ~1–2 GB system RAM, ~0 idle CPU.
  ~9% of the **16 GB** RTX 5000 Ada Laptop GPU (validated 2026-07-14: 2933/16376 MiB used with Ollama also
  resident). Headroom to swap in bge-large (~1.3 GB) with no architecture change — only the VRAM number moves.
- LAN-only, dev-password/secret per lab convention; joins whatever mesh policy the stores require.

### 3.2b Manifest table — decoupled from the pgvector store (decided during Step 4)

`rag_documents` is doing double duty today: the shared **hash-gate manifest** (read by `hash_check` + `aidlc_kb`)
AND the **pgvector store's own document table** (written by `pgvector_write` for docs, `aidlc_kb` for KB, with an
`rag_chunks` FK). Coupling the producer's change-detection to a store table would race the pgvector consumer.

Decision: the producer gets its **own** tiny table **`rag_manifest(source_path PRIMARY KEY, content_hash)`** as
its private change-detection + prune state. `rag_documents` stays fully owned by the pgvector consumer (docs) and
`aidlc_kb` (KB). Because `source_document` never yields `aidlc-kb/` paths **and** the manifest query filters
`source_path NOT LIKE 'aidlc-kb/%'`, the producer **structurally cannot** tombstone the KB corpus — the old
`domain=aidlc-kb` prune-exclusion guard is now an invariant of the data model, not a runtime check.

### 3.3 Producer — indexing worker

- Triggered by Dagster with the manifest. For each changed `source_path`: read file → chunk → embed via the
  rogueone service in batches → publish records to `rag.chunks`. **One batch in flight at a time** — vectors are
  published and dropped immediately, so peak memory is constant regardless of corpus size. Satisfies **I1, I2**.
- **Chunking** = LlamaIndex primitives: `SentenceSplitter` (size 1500 / overlap 200) for code; H2-section split
  for markdown — preserving the current `chunks.py` semantics (`chunk_index`, `chunk_title`, `source_path`,
  `source_name`, `kind`).
- **Prune** — the producer holds the run's full current-path set and the previous manifest; for every
  `source_path` present before but absent now, it publishes a **tombstone** record. Satisfies **I5** without a
  whole-state scan of any store (see §4.1).
- Runs as a Dagster op (light now) or a dedicated k8s Job. Either way it is a reference-boundary compute unit.

### 3.4 Bus — Redpanda topic `rag.chunks`

- Avro via the existing schema registry. **Partition key = `source_path`** so a document's chunks are ordered
  and co-located, and a tombstone for a doc is ordered after its upserts.
- Two record types (one schema, `op` discriminator):
  - `upsert`: `source_path, chunk_index, chunk_text, vector[float], content_hash, source_name, kind, run_id`
  - `tombstone`: `source_path, op=delete, run_id`
- Retention long enough to **replay-rebuild** any single store (days/weeks; small payloads).

### 3.5 Consumers — five independent deployments

- One consumer group per store: `qdrant`, `weaviate`, `pgvector` (vector upsert), `neo4j` (MERGE Document/Chunk
  nodes + relationships), `opensearch` (lexical/hybrid index).
- Each applies upserts and tombstones to its own store and commits offsets independently. One store down does not
  block the others; retry = its group resumes; rebuild-one-store = reset that group's offset. Satisfies **I4**.

## 4. The two hard seams, resolved

### 4.1 Orphan prune as tombstones (not a whole-state pass)

The whole-state diff lives in exactly one place — the producer, which knows the current-path set and the previous
manifest. It emits a **tombstone** per removed `source_path`. Each consumer handles tombstones as
delete-by-`source_path`. Prune is therefore per-store-isolated and replayable, identical in shape to a write. No
end-of-run reconcile job, no per-store scans. The previous manifest is persisted by the producer (small: paths +
hashes) — in Postgres or object storage, keyed by index name.

### 4.2 Effectively-once (no EOS transactions)

- `upsert` is idempotent: keyed by `(source_path, chunk_index)` → overwrite.
- `tombstone` is idempotent: delete-by-`source_path` → delete-if-exists.
- Per-doc ordering is guaranteed by the `source_path` partition key (upserts before the doc's tombstone).

At-least-once delivery + idempotent keys = effectively-once, with no Kafka transactions to operate.

## 5. Avro schema (sketch)

```
record RagChunk {
  string  source_path;
  string  op;              // "upsert" | "delete"
  int     chunk_index;     // upsert only
  string  chunk_title;     // nullable
  string  chunk_text;      // upsert only
  array<float> vector;     // upsert only, dim = 384 (bge-small)
  string  content_hash;    // upsert only
  string  source_name;
  string  kind;            // "markdown" | "code"
  string  run_id;
}
```

## 6. Migration (strangler)

1. Stand up `rag.chunks` topic + Avro schema; deploy the five consumers (idempotent, so safe to run against the
   live stores).
2. Deploy the rogueone embedding service.
3. Deploy the producer; wire the Dagster sensor to trigger it with the manifest.
4. Run new and old paths side-by-side against the same stores — idempotent keys make this safe — until parity is
   confirmed.
5. Cut the sensor over; **retire** the in-process assets: `chunks`, `embeddings`, `qdrant_write`,
   `weaviate_write`, `pgvector_write`, `neo4j_write`, `opensearch_write`, and the `SentenceTransformerResource`
   in the ingestion path.

## 7. What this retires / changes

- **Retired**: the five `*_write` assets + `embeddings`/`chunks` assets as the write path; the in-orchestrator
  sentence-transformer load.
- **Dagster** keeps: the sensor/`hash_check` incrementality, run history, lineage (now derived from the returned
  manifest/counts), scheduling, retry of the producer trigger.
- **DataHub lineage**: `embeddings` node is replaced by the `rag.chunks` topic as the fan-out hub — arguably a
  truer lineage picture (one source stream → five stores).

## 8. Costs & constraints (honest)

- **rogueone**: ~1–1.5 GB VRAM reserved 24/7 (warm), ~1–2 GB system RAM. Negligible on a 32 GB card next to
  Ollama; the only real cost is the standing reservation. Scale-to-zero (KEDA) is possible later but trades the
  warm-model benefit for cold-start latency — keep it warm.
- **Operational surface**: one topic + one producer + five consumer deployments + one embed service, versus one
  Dagster job. This is the price of decoupling, replayability, and constant memory — and the platform capability
  this demonstrates.
- **K8sRunLauncher**: optional after this lands (§3.1). Recommend keeping it for the other heavy in-process jobs;
  confirm during implementation.
- **$0 / self-hosted**: all components already in-stack (Redpanda, schema registry, rogueone GPU, the five
  stores, Dagster). No new paid services.

## 9. Open decisions to confirm

1. Producer as a **Dagster op** (simplest; light now) vs. a **dedicated k8s Job** (cleaner reference boundary).
   Recommend: Dagster op first, since it is already light — promote to a Job only if it grows.
2. Previous-manifest store for the prune diff: **Postgres table** vs. **object storage**. Recommend Postgres
   (transactional, queryable).
3. Keep **K8sRunLauncher** for the other jobs (recommend yes) or defer.
4. Consumer packaging: five separate images vs. one image / five deployments with a `STORE` env. Recommend the
   latter (one codebase, per-store config) unless a store's client deps conflict.

## 10. Implementation checklist (locked decisions: producer=Dagster op · prune-manifest=Postgres · keep K8sRunLauncher · consumers=one image + STORE env)

- [ ] **Step 1 — Topic + schema.** Create Redpanda topic `rag.chunks` (partition key `source_path`); register the
      `RagChunk` Avro schema. Validate: topic listed, schema in registry.
- [x] **Step 2 — Embedding service (rogueone).** DONE 2026-07-14. `services/rag-embed/` warm `bge-small-en-v1.5`
      `/embed` on GPU (systemd `rag-embed.service`, port 8900). Validated: `dim 384 device cuda`, 384-float
      vectors, 16 GB card at 18% with Ollama.
- [x] **Step 3 — One consumer (qdrant), end to end.** DONE 2026-07-14. `services/rag-index/` (one image, many
      stores; `STORE` env dispatch) + `k8s/data-mesh/rag-index-qdrant.yaml` (sidecar-off streaming plane). Consumer
      ensures the topic on startup (folds in Step 1); `delete` op = replace-clear (changed) AND tombstone (removed).
      Validated via `probe.py`: upsert→2 points, delete→0. Gotchas fixed: unknown-topic crash-loop (ensure + tolerate
      ConsumeError), `TOPIC_ALREADY_EXISTS` guard by error CODE not message string.
- [x] **Step 4 — Producer (Dagster op).** DONE 2026-07-14. `assets/rag_stream_produce.py` — reuses the existing
      chunkers, embeds via the rogueone GPU service (by IP: `*.weyland.lab` wildcards to the ingress), publishes
      delete-clears + upserts + tombstones to rag.chunks; `rag_manifest` (its own table) = change-detection + prune
      state, decoupled from the pgvector `rag_documents` (§3.2b). Validated by exact math: 475 changed → 2370
      upserts + 475 clears + 4 probe = 2849 topic records; consumer lag 0; qdrant docs-only = 2370; re-run gate =
      0 published (HWM flat). Trigger: `dagster asset materialize --select "*rag_stream_produce"` (a `rag_stream_job`
      lands in Step 6). NOTE deprecation: switch `context.run_id` → `context.run.run_id`.
- [ ] **Step 5 — Remaining consumers.** weaviate, pgvector, neo4j, opensearch (same image, `STORE` env).
      Validate each end to end.
- [ ] **Step 6 — Dagster wiring + retire.** Sensor emits manifest + triggers producer; enable K8sRunLauncher for
      the other heavy jobs; retire `chunks`/`embeddings`/`*_write` assets after side-by-side parity; update
      docs/arch.
```
