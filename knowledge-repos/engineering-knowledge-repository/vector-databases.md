---
id: vector-databases
tags: [tooling, ai-ml, backend, database]
surfaces-at: [application-design, infrastructure-design]
related: [embeddings, semantic-search, retrieval-augmented-generation, database-indexing]
complexity: intermediate
---

# Vector Databases

## What It Is
Databases purpose-built for storing, indexing, and querying high-dimensional embedding vectors at scale. Unlike traditional databases that find rows by exact or range matching, vector databases find the approximate nearest neighbors (ANN) — the vectors most similar to a query vector. They underpin semantic search, RAG pipelines, recommendation systems, and any application requiring similarity-based retrieval over large corpora.

## When to Apply
- RAG pipelines storing embedded document chunks for retrieval
- Semantic search over large document corpora where keyword search is insufficient
- Recommendation systems using user/item embeddings
- Any application storing more than a few thousand embeddings where in-memory search is impractical

## When Not to Apply
- Small corpora (< ~10k vectors) — in-memory libraries (FAISS, Chroma) are simpler and sufficient
- Applications where exact matching is required — vector databases find approximate neighbors, not exact ones

## Key Concepts
- **ANN (Approximate Nearest Neighbor)**: Trading perfect accuracy for speed. ANN algorithms (HNSW, IVF) find the closest vectors without exhaustive search. Recall (what % of true nearest neighbors are returned) is the accuracy tradeoff
- **HNSW (Hierarchical Navigable Small World)**: The dominant ANN index structure — graph-based, high recall, fast query. Used by most production vector databases
- **IVF (Inverted File Index)**: Partitions vectors into clusters; queries search only relevant clusters. More memory-efficient than HNSW; slightly lower recall
- **Metadata Filtering**: Most vector databases support filtering by scalar metadata alongside vector similarity — `WHERE category = 'finance' ORDER BY similarity`. Essential for multi-tenant and filtered retrieval
- **pgvector**: PostgreSQL extension for vector storage and ANN search. Best choice when you're already on PostgreSQL — no additional infrastructure, full SQL capabilities, transactions. Suitable up to ~1M vectors with proper indexing
- **Pinecone**: Managed vector database — scales to billions of vectors, serverless option, built-in metadata filtering. Zero operational overhead; vendor lock-in
- **Weaviate**: Open-source vector database with hybrid search (vector + BM25) built in, GraphQL API, and modules for auto-embedding
- **Qdrant**: Open-source, Rust-based, high performance, supports named vectors (multiple vector spaces per record). Good self-hosted option
- **Chroma**: Lightweight, embeddable vector store for development and small-scale production. Easy to get started; not designed for large-scale
- **Namespace / Collection Isolation**: Multi-tenant applications must isolate vectors per tenant — either separate collections or metadata-based filtering. Critical for data privacy

## In Practice
Method uses pgvector for applications already on PostgreSQL with corpora up to ~500k vectors. Pinecone for larger scale or when operational simplicity is the priority. Weaviate when hybrid search is required out of the box. HNSW index is used by default. Metadata always includes tenant ID and document source for filtered retrieval and attribution.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Vector Databases**: Store and query embeddings at scale. Use pgvector if you're already on PostgreSQL — no new infrastructure, handles most use cases up to ~500k vectors. Pinecone for large scale or managed simplicity. Always include metadata (source, tenant ID, created_at) alongside vectors — you need it for filtering and attribution. HNSW indexing is the default for high-recall, fast-query use cases. Multi-tenant apps must isolate vectors per tenant — filter by metadata or use separate collections. Pin your embedding model; switching requires re-embedding everything. → `engineering-knowledge-repository/vector-databases.md`

## Related Entries
- [Embeddings](embeddings.md) — vectors stored in vector databases are produced by embedding models
- [Semantic Search](semantic-search.md) — vector databases power semantic search retrieval
- [Retrieval-Augmented Generation](retrieval-augmented-generation.md) — RAG retrieval queries the vector database
- [Database Indexing](database-indexing.md) — vector indexes (HNSW, IVF) are analogous to traditional database indexes
