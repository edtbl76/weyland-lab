# Flow: Backend Selection / Dispatch (detail of RAG retrieval)

Zoom-in on `/context/*`: how one of the 4 vector backends is chosen. Selection is a **single-dispatch** per
request — a `backend` param (query param for `/context/search`, body field for `/context/ask`), defaulting to
`pgvector`. There is **no fan-out / compare-all mode**: `backend=all` (or any unknown value) is rejected with a
`400`. The chosen backend's function embeds the query (bge) and runs the vector search; all hops are mTLS under
the mesh (see [flow-mesh-mtls.md](flow-mesh-mtls.md)). For the end-to-end query+generate path see
[flow-rag-query.md](flow-rag-query.md).

```mermaid
sequenceDiagram
    participant Cl as Client
    participant TS as tool-server /context/search
    participant Fn as Selected backend fn (SEARCH_FNS[backend])
    participant Emb as bge embedding
    participant Back as pgvector | qdrant | weaviate | neo4j
    Cl->>TS: GET /context/search {query, backend=pgvector (default)}
    alt backend not in {pgvector,qdrant,weaviate,neo4j}
        TS-->>Cl: 400 (e.g. backend=all rejected)
    else valid backend
        TS->>Fn: dispatch SEARCH_FNS[backend]
        Fn->>Emb: embed(query)
        Fn->>Back: vector search top-k
        Back-->>Fn: chunks
        Fn-->>TS: ranked chunks
        TS-->>Cl: results
    end
```
