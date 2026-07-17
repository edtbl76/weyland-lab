# Flow — RAG end-to-end (doc change → index → retrieve → eval)

The single arc that starts from an **actual doc edit** and ends on a **leaderboard number**, threading four
already-validated component flows into one story: a changed doc is chunked, embedded **once** on the rogueone GPU
(`rag-embed`, `192.168.1.230:8900`), and streamed through Redpanda `rag.chunks` into all five stores
([flow-rag-stream.md](flow-rag-stream.md)); the tool-server retrieves the new chunk and synthesizes a grounded
answer via Ollama ([flow-rag-query.md](flow-rag-query.md)); an eval run asks a corpus-grounded question set across
all 6 local models ([flow-eval.md](flow-eval.md)); and an LLM-judge panel scores the run so the leaderboard
tightens ([flow-eval-scoring.md](flow-eval-scoring.md)). Nothing here is new mechanism — it is the seam between
the four flows made explicit. See [../demos/rag-e2e.md](../demos/rag-e2e.md).

**Current reality:** Ollama (generator + judges) runs on **rogueone** (`192.168.1.230`, RTX 5000 Ada), moved off
the retired CT-102 in B79. The embedding service `rag-embed` is a separate native systemd unit on the same box
(`:8900`). `kubectl` runs on mother; the tool-server is a NodePort at `mother:30080`.

## Sequence

```mermaid
sequenceDiagram
    actor Author
    participant DAG as Dagster rag_stream_produce
    participant EMB as rag-embed (rogueone :8900)
    participant TOPIC as rag.chunks (Redpanda)
    participant STORE as 5 store consumers (qdrant/weaviate/pgvector/neo4j/opensearch)
    participant TS as tool-server /context (mother :30080)
    participant OLL as Ollama (rogueone :11434)
    participant PG as Postgres eval_*

    Author->>DAG: edit a doc, then materialize rag_stream_produce
    DAG->>EMB: POST /embed (changed chunks, batch 64)
    EMB-->>DAG: 384-dim vectors
    DAG->>TOPIC: delete-clear + upsert per chunk
    STORE->>TOPIC: consume, apply to each store (lag → 0)
    Author->>TS: POST /context/ask (question that hits the edit)
    TS->>STORE: vector/graph retrieve top-k
    TS->>OLL: synthesize grounded answer
    OLL-->>Author: answer + sources (cites the edited doc)
    Author->>TS: POST /evals/run (10 Q × 6 models)
    TS->>PG: eval_questions + eval_results (60 rows)
    Author->>TS: POST /evals/score (LLM-judge panel)
    TS->>OLL: judge faithfulness / relevancy
    TS->>PG: eval_scores
    Author->>TS: GET /evals/leaderboard
    TS-->>Author: panel-averaged leaderboard number
```

The three-judge panel tightens the field to roughly **0.75–0.82** faithfulness, with `gpt-oss:20b` the most
defensible RAG pick (top-2 under every judge, and not itself a judge → zero self-bias). Per-leg detail lives in
the four component flows and their demos.
