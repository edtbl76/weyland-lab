# Flow: Kindle library → KM RAG (B165)

"Log in once, script the rest." A throwaway Windows VM on rogueone extracts DRM-stripped EPUB/TXT to MinIO; the
weyland-dagster pipeline chunks → bge-base embeds → writes a `kindle` Qdrant/Weaviate collection; query via the
operator/MCP, graded against a golden set. The only manual step is the one-time Amazon sign-in.

```mermaid
flowchart TD
    subgraph VM[Throwaway Windows VM on rogueone]
        L[Sign into Kindle-for-PC<br/>manual, once] --> SY[library syncs to disk]
        SY --> EX[kindle-extract.ps1<br/>calibredb add = DeDRM strips on import<br/>then export EPUB plus TXT]
    end
    EX --> MIN[(MinIO kindle-corpus)]
    MIN --> LAND[dagster datasets_kindle_land]
    LAND --> CH[section-aware chunker<br/>chunks.py]
    CH --> EMB[bge-base 768 embed]
    EMB --> QD[Qdrant plus Weaviate<br/>kindle collection<br/>payload title author ASIN]
    QD --> Q[query via operator or MCP]
    QD --> EV[eval golden set<br/>graded via eval matrix]
    LAND --> DH[DataHub dataset plus lineage]
```

Extraction runbook: [runbooks/kindle-rag.md](../runbooks/kindle-rag.md) · demo: [demos/kindle-rag.md](../demos/kindle-rag.md).
Reuses the finance-filings RAG pattern (B113), bge-base retrieval (B74), the vector stores (B1), the eval golden
set (B96). The book #1 gate (prove one decrypt before batching) lives in the runbook.
