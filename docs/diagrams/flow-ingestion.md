# Flow: Ingestion (repo → 4 vector backends)

> **SUPERSEDED 2026-07-14 by [flow-rag-stream](flow-rag-stream.md).** The in-process fan-out to the vector
> backends shown below is RETIRED. The write path is now a streaming producer (`rag_stream_produce`) that
> publishes to Redpanda `rag.chunks`, consumed by 5 independent store consumers (B-RAG-STREAM). The clone +
> per-file hash-gate + chunk + embed steps are retained (now inside `rag_stream_produce`, embedding on the
> rogueone GPU service). Walkthrough: [demos/rag-stream.md](../demos/rag-stream.md). This diagram is kept for
> history only.

**Live since 2026-06-15 (B25b).** Dagster shallow-clones the **GitHub repo** each run and ingests the whole
`docs/` tree (markdown) **+** `nodes/` code/manifests — decoupled from any one workstation. Per-file hash-gate;
markdown chunks by H2, code by fixed-size+overlap. (Replaced the old SSH/SFTP single-Obsidian-note source + the
rogueone inotify watcher, both retired.)

```mermaid
sequenceDiagram
    participant Cron as Dagster schedule (*/15)
    participant Dag as Dagster (mother)
    participant GH as GitHub (edtbl76/weyland-lab)
    participant PG as Postgres/pgvector
    participant Vec as Qdrant + Weaviate + Neo4j
    Cron->>Dag: launchRun (weyland_ingestion_job)
    Dag->>GH: git clone --depth 1 (public repo)
    Dag->>Dag: collect docs/**/*.md + nodes/** (exclude secrets/binaries/locks)
    Dag->>Dag: SHA256 content_hash per file
    Dag->>PG: compare stored hash per source_path
    loop each CHANGED file
        Dag->>Dag: chunk (md=H2 / code=fixed-size+overlap) + bge embed
        Dag->>PG: pgvector_write (upsert by source_path)
        Dag->>Vec: qdrant_write + weaviate_write + neo4j_write
    end
```

**Trigger:** the `*/15` cron (hash-gate makes a no-change run a cheap no-op). Near-real-time push-trigger is
deferred — **B30** (self-hosted GitHub Actions runner fires `launchRun` on push).
**Reconciliation:** each run prunes sources no longer in the repo — every write asset deletes entries whose
`source_path` isn't in the current collected set, across all 4 backends (skipped if the clone collected
nothing, so a bad run never wipes the store).
