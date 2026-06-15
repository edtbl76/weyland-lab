# Flow: Ingestion (docs -> 4 vector backends)

Current flow: Obsidian note on rogueone -> Dagster -> 4 backends. **B25 will replace the SSH/SFTP source with git-pull of the full docs/ tree.**

```mermaid
sequenceDiagram
    participant Vault as Obsidian note (rogueone)
    participant Watch as inotify watcher (rogueone)
    participant Dag as Dagster (mother)
    participant PG as Postgres/pgvector
    participant Vec as Qdrant + Weaviate + Neo4j
    Vault->>Watch: file change (30s debounce)
    Watch->>Dag: GraphQL launchRun (weyland_ingestion_job)
    Dag->>Vault: SSH read markdown (paramiko, pinned host key)
    Dag->>Dag: SHA256 content_hash
    Dag->>PG: compare stored hash
    alt content unchanged
        Dag-->>Watch: downstream skipped (hash gate)
    else content changed
        Dag->>Dag: H2 chunk + bge embed
        Dag->>PG: pgvector_write
        Dag->>Vec: qdrant_write + weaviate_write + neo4j_write
    end
```

**B25 target flow:** git clone/pull docs/ -> chunk all .md files -> same 4-backend write pipeline. inotify watcher on Obsidian file will be retired.
