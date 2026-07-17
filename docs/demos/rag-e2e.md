# Demo — RAG end-to-end (doc change → index → retrieve → eval)

> **Pending live end-to-end validation run.** Every command below is real and pulled from the four component
> demos it threads, but this cross-system walkthrough has **not** yet been executed straight through against
> live infra.

One reproducible story that starts from an **actual doc edit** and ends on a **leaderboard number**. It threads
four already-validated component demos into a single arc:

1. **[rag-stream.md](rag-stream.md)** — a changed doc is chunked, embedded once on the rogueone GPU, and streamed
   through Redpanda `rag.chunks` into all five stores.
2. **[rag-query.md](rag-query.md)** — the tool-server retrieves the new chunk and synthesizes a grounded answer.
3. **[eval.md](eval.md)** — a fresh eval run asks a corpus-grounded question set across all 6 local models.
4. **[eval-scoring.md](eval-scoring.md)** — an LLM-judge panel scores the run and the leaderboard tightens.

Nothing here is new mechanism — it is the seam between four demos made explicit. Read each component demo for the
per-step detail; this file is the connective tissue and the single before/after evidence trail.

**Current reality:** Ollama (generator + judges) runs on **rogueone** (`192.168.1.230`, RTX 5000 Ada), moved off
the retired CT-102 in B79. The embedding service `rag-embed` is a separate native systemd unit on the same box
(`:8900`).

**Sequence:** [flow-e2e-rag.md](../diagrams/flow-e2e-rag.md)

## Prerequisites

The union of the four component demos' prerequisites — confirm each is up before threading:

- **rogueone** (`192.168.1.230`) — `rag-embed.service` on `:8900` (bge-small-en-v1.5) **and** Ollama on
  `:11434` / `ollama.weyland.lab` (6 models: generator + judge panel).
- **Redpanda** (`redpanda-0`, ns `data-mesh`) — Kafka `:9092`, schema registry `:8081`, topic `rag.chunks`.
- **Five store consumers** (`rag-index-*`) draining `rag.chunks` (see [rag-stream.md](rag-stream.md) for the
  ns / sidecar split).
- **tool-server** — `http://mother:30080` (NodePort) exposing `/context/*` and `/evals/*`.
- **weyland-postgres** (ns `weyland`) — `rag_manifest` + the `eval_*` schema (`scripts/eval-schema.sql` applied).
- **Dagster** (`dagster.weyland.lab`) — `weyland_pipeline` code location in `deploy/dagster-user-code`.
- `kubectl` runs on **mother** (`emangini@mother`); the embed box is `edwardmangini@rogueone`.

## UI walkthrough

**Step 1 — make a real change and index it.**
1. Edit a tracked doc (e.g. add a distinctive sentence to `docs/runbooks/mesh-mtls.md`). This is the change the
   whole arc will chase.
2. Open `https://dagster.weyland.lab` → Assets → `rag_stream_produce` → **Materialize**. The run logs
   `N changed docs (M chunk upserts), K removed`.
3. Open `https://redpanda.weyland.lab` (Console) → Topics → **`rag.chunks`** → Messages — the new chunk shows
   `op=upsert`, its `source_path`, and the 384-float vector.
4. Console → Consumer Groups → confirm `rag-index-qdrant` / `-weaviate` / `-pgvector` / `-neo4j` / `-opensearch`
   all drain to **lag 0**.

**Step 2 — retrieve the change.**
5. Open `http://mother:30080/docs` (tool-server Swagger) → **POST `/context/ask`** → Try it out with a body that
   targets your edit, e.g. `{"query":"How does the mesh enforce mTLS?","backend":"pgvector"}`. **Execute** — the
   answer should be grounded in the doc you just edited, with it listed in `sources`.

**Step 3 — evaluate.**
6. Trigger `/evals/run` (CLI below is the reliable path); watch `weyland_eval_job` under **Runs** in Dagster.
7. Trigger `/evals/score`; watch `weyland_eval_score_job`.
8. Read `GET /evals/leaderboard` from the Swagger page — the panel-averaged number is the arc's endpoint.

## CLI walkthrough

Kubectl runs on **mother**. The embed/Ollama box is `rogueone`.

**Step 0 — health of the two remote services (rogueone):**
```
[rogueone] curl -s http://localhost:8900/health
[rogueone] curl -s http://localhost:11434/api/tags | head -c 300 ; echo
```
```
[mother] curl -s http://192.168.1.230:8900/health
[mother] kubectl -n data-mesh exec redpanda-0 -- rpk cluster health
```

**Step 1 — index the changed doc** (edit a tracked doc first, then):
```
[mother] kubectl -n weyland exec deploy/dagster-user-code -- dagster asset materialize -m weyland_pipeline --select "*rag_stream_produce"
```
```
[mother] kubectl -n data-mesh exec redpanda-0 -- rpk topic consume rag.chunks --num 1
[mother] kubectl -n data-mesh exec redpanda-0 -- rpk group describe rag-index-qdrant
[mother] curl -s http://mother:30083/collections/weyland_chunks
```
> `TODO: verify` the exact in-pod `dagster asset materialize` invocation (module flag `-m weyland_pipeline` =
> the code-location name) — carried over from [rag-stream.md](rag-stream.md).

**Step 2 — retrieve the new content** (swap `backend=` for `qdrant`/`weaviate`/`neo4j` to prove every store got it):
```
[mother] curl -s -X POST "http://mother:30080/context/search?backend=pgvector" -H 'Content-Type: application/json' -d '{"query":"How does the mesh enforce mTLS?","limit":5}'
[mother] curl -s -X POST http://mother:30080/context/ask -H 'Content-Type: application/json' -d '{"query":"How does the mesh enforce mTLS?","backend":"pgvector"}'
```

**Step 3 — run the eval matrix** (~40–60 min, 10 Q × 6 models):
```
[mother] curl -s -X POST http://mother:30080/evals/run
```
```
[mother] kubectl exec -n weyland deploy/weyland-postgres -- sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, status, question_count FROM eval_runs ORDER BY id DESC LIMIT 3;"'
```

**Step 4 — score and read the leaderboard number:**
```
[mother] curl -s -X POST http://mother:30080/evals/score
[mother] curl -s http://mother:30080/evals/leaderboard
```
Straight from Postgres (latest run resolved inline):
```
[mother] kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -d weyland -c "SELECT model, round(avg(score) FILTER (WHERE metric='faithfulness')::numeric,3) AS faithful FROM eval_results r JOIN eval_scores s ON s.result_id = r.id WHERE r.run_id = (SELECT max(id) FROM eval_runs) GROUP BY model ORDER BY faithful DESC NULLS LAST;"
```

## Expected result

- **Indexed:** `rag.chunks` carries the new upsert; all five consumer groups drain to lag 0; qdrant
  `weyland_chunks` gains points for the edited doc's chunks (per [rag-stream.md](rag-stream.md)).
- **Retrieved:** `/context/ask` returns `{answer, model, backend, sources}` grounded in the edit, with the edited
  doc in `sources` — end-to-end proof the change is now queryable.
- **Evaluated:** a new `eval_runs` row (`question_count = 10`), `eval_results` with **60 rows** (10 × 6), 0 errors
  on a healthy run.
- **Scored:** `eval_scores` populated, `eval_runs.status = 'scored'`, and the panel-averaged leaderboard renders.
  Runbook Run-3 finding: the 3-judge panel tightens the field to **0.75–0.82**, with `gpt-oss:20b` the most
  defensible RAG pick (top-2 under every judge, and not itself a judge → zero self-bias).

## Cleanup / teardown

Each leg cleans up per its own demo — do them in reverse order:

- **Eval scores** (this arc's created data): delete scores → results → run for the latest id, per
  [eval-scoring.md](eval-scoring.md) and [eval.md](eval.md):
```
[mother] kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -d weyland -c "DELETE FROM eval_scores WHERE result_id IN (SELECT id FROM eval_results WHERE run_id=(SELECT max(id) FROM eval_runs));"
[mother] kubectl exec -n weyland deploy/weyland-postgres -- sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM eval_results WHERE run_id = (SELECT max(id) FROM eval_runs);"'
[mother] kubectl exec -n weyland deploy/weyland-postgres -- sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM eval_runs WHERE id = (SELECT max(id) FROM eval_runs);"'
```
- **Retrieval** ([rag-query.md](rag-query.md)) is read-only — nothing to undo.
- **The index** is the **live RAG index** (production data, not throwaway) — do **not** casually tear it down. If
  your doc edit was itself throwaway, revert the doc and re-materialize `rag_stream_produce` so the chunk is
  re-published as changed (or tombstoned if removed). The full destructive reset is in
  [rag-stream.md](rag-stream.md).
