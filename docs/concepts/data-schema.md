# Data Schema — RAG + Eval Stores

The schemas behind weyland's retrieval and evaluation stores, in one place. **Validated against ground
truth** (2026-06-15): live Qdrant + Weaviate APIs, the Dagster pipeline write code, and
`scripts/eval-schema.sql` — *not* the (retired) Obsidian note.

The same logical chunk is written to **four backends in one Dagster run**, each keyed by `source_path` so
documents are independently upsertable (delete-by-source → re-insert). Embeddings are
**`BAAI/bge-small-en-v1.5`, 384-dim, L2-normalized** — baked into both the tool-server and Dagster images so
ingestion and query embed identically.

> **Schema provenance:** the `eval_*` tables have committed DDL (`scripts/eval-schema.sql`). The `rag_*`
> tables do **not** — they're created implicitly by the pipeline. *Gap / follow-up:* add a `rag-schema.sql`
> for parity. `rag_*` columns below are from the pipeline write code, confirmed against the live DB
> (2026-06-15). **The live DB also holds 4 tables with NO repo DDL — `services`, `machines`, `models`,
> `memory_facts` — created out-of-band (see §5).**

---

## 1. Postgres / pgvector — the spine

### RAG tables (implicit DDL — from pipeline write code)
**`rag_documents`** — one row per source document (keyed by `source_path`):

| column | type | notes |
|---|---|---|
| `id` | BIGSERIAL PK | FK target for chunks |
| `name` | TEXT | = `source_name` (filename without `.md`) |
| `source_type` | TEXT | `"markdown"` |
| `source_path` | TEXT **UNIQUE** | upsert key (`ON CONFLICT (source_path)`) |
| `content_hash` | TEXT | SHA256 of content — the change-gate |
| `metadata` | JSONB | currently `{}` |
| `updated_at` | TIMESTAMPTZ | bumped on upsert |

**`rag_chunks`** — H2-split chunks with vectors (old chunks deleted then re-inserted per document):

| column | type | notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `document_id` | BIGINT FK → `rag_documents(id)` | |
| `chunk_index` | INT | order within document |
| `content` | TEXT | full section (heading + body) |
| `embedding` | `vector(384)` | pgvector, bge, normalized |
| `metadata` | JSONB | `{"title": <chunk_title>}` when present |

### Eval tables (`scripts/eval-schema.sql`, B4 — committed DDL, idempotent)
Reuses the same DB; no new database.

- **`eval_runs`** — one row per leaderboard run: `id`, `created_at`, `status` (`running|complete|failed`),
  `models TEXT[]`, `metrics TEXT[]`, `question_count`, `notes`.
- **`eval_questions`** — generated questions per run: `id`, `run_id`→eval_runs (CASCADE), `question`,
  `question_type`, `reference_answer`, `reference_contexts JSONB`, `created_at`.
- **`eval_results`** — one RAG output per (question × model): `id`, `run_id`, `question_id`, `model`,
  `backend` (default `pgvector`), `answer`, `contexts JSONB` (grounding set), `latency_ms`, `error`,
  `created_at`.
- **`eval_scores`** — LLM-as-judge score per (result × metric × judge): `id`, `result_id`→eval_results
  (CASCADE), `metric` (**`faithfulness | answer_relevancy | context_relevancy`** — actual metrics; the SQL
  comment's "ragas" is stale, Ragas was rejected in B4), `judge` (judge model; **panel of ≥3**), `score`
  DOUBLE PRECISION, `UNIQUE (result_id, metric, judge)`.
- **`eval_leaderboard`** (VIEW) — `AVG(score)` per (`run_id`, `model`, `metric`) across judges; read directly
  by `GET /evals/leaderboard`.
- Indexes: `idx_eval_results_run`, `idx_eval_results_model`, `idx_eval_scores_result`.

---

## 2. Qdrant — collection `weyland_chunks` *(live-validated)*
- **Vectors:** size **384**, distance **Cosine**. HNSW `m=16`, `ef_construct=100`. `on_disk_payload=true`.
- **Point id:** `uuid5(source_path:chunk_index)` (deterministic → idempotent upsert).
- **Payload:** `source_path`, `source_name`, `chunk_index`, `chunk_title`, `content`.
- Upsert pattern: delete points where `payload.source_path == <doc>`, then upsert the doc's chunks.

## 3. Weaviate — classes `WeylandChunk` + `WeylandDocument` *(live-validated)*
- `vectorizer: none` (we supply bge vectors), HNSW **cosine**, `efConstruction=128`, `maxConnections=32`.
- **`WeylandChunk`** props: `source_path`, `chunk_index` (int), `chunk_title`, `content`; **references**:
  `hasDocument` → WeylandDocument, `previousChunk`/`nextChunk` → WeylandChunk (sequential chain).
- **`WeylandDocument`** props: `source_path`, `source_name`, `name`.

## 4. Neo4j — `Document` + `Chunk` (GraphRAG foundation) *(from pipeline code)*
- **`Document`** node: `source_path`, `source_name`, `name`, `ingested_at`.
- **`Chunk`** node: `source_path`, `chunk_index`, `chunk_title`, `content`, `embedding` (array).
- **Relationships:** `(Chunk)-[:BELONGS_TO]->(Document)`; `(Chunk)-[:NEXT]->(Chunk)` (sequential chain).
- Vector index on `Chunk.embedding` (bootstrap: `scripts/neo4j-vector-index-bootstrap.cypher`).
- *Not live-validated here (needs Bolt auth) — confirm with a Cypher `CALL db.schema.visualization()` if drift
  is suspected.*

---

## 5. Out-of-band inventory schema (live, no repo DDL)
Live on the DB (confirmed 2026-06-15) but defined **nowhere in the repo**. On inspection these are NOT cruft —
they're a **deliberately-designed, normalized system-inventory schema** (FKs, unique constraints,
`set_updated_at` triggers):

- **`machines`** — `name`, `role`, `hostname`, `ip inet`, `notes` (host inventory)
- **`services`** — `name`, `machine_id`→`machines`, `role`, `endpoint`, `status` (services per machine)
- **`models`** — `name`, `provider`, `served_by_service_id`→`services`, `role`, `status` (models per service)
- **`memory_facts`** — `key`, `value jsonb`, `category`, `source` (key/value agent memory)

So `machines → services → models` is a **structured relational mirror of `docs/hosts.md` + `docs/api.md`**, and
`memory_facts` is an agent long-term memory store. Currently **unpopulated/stale**. **Ownership/intent
unconfirmed** — OpenClaw references them, but the schema is general infra knowledge, not OpenClaw-specific.

**The DDL is uncommitted** — it's in neither the weyland repo nor the OpenClaw clone (`nodes/openclaw`); it
exists **only on the live DB** (created ad-hoc, never version-controlled). That's a gap to fix.

**Disposition (confirmed 2026-06-15):**
- `machines / services / models` → **adopt for the data-mesh system-inventory product (B1)** (user-confirmed
  useful). **Action:** dump the live DDL into a tracked repo migration, then decide whether `hosts.md`/`api.md`
  generate *from* this inventory or feed *into* it.
- `memory_facts` → **orphan.** A generic `key/value/category/source` store that **no code anywhere references**
  (repo or OpenClaw clone), currently empty, origin unknown. Repurpose as a structured memory store or drop — TBD.

> Corrects three earlier assumptions: `services` is not a phantom; these aren't disposable OpenClaw cruft; and
> the schema is **not in any source** — uncommitted, live-DB-only.

## Live Postgres state (confirmed 2026-06-15)
`\dt` → **platform:** `rag_documents`, `rag_chunks` · `eval_runs`, `eval_questions`, `eval_results`,
`eval_scores` (+ `eval_leaderboard` view). **out-of-band (OpenClaw, §5):** `services`, `machines`, `models`,
`memory_facts`.
