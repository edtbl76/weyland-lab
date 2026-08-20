---
id: semantic-search
tags: [pattern, ai-ml, backend, database]
surfaces-at: [application-design, functional-design]
related: [embeddings, vector-databases, retrieval-augmented-generation, caching-strategies]
complexity: intermediate
---

# Semantic Search

## What It Is
Search that finds results based on meaning rather than exact keyword matching. A semantic search for "affordable cars under 20k" returns results about "budget vehicles below $20,000" — conceptually related but lexically different. Powered by embedding models that convert queries and documents into vectors, then retrieving the documents whose vectors are closest to the query vector. Complements or replaces traditional full-text search (Elasticsearch, Postgres `tsvector`) for use cases requiring conceptual matching.

## When to Apply
- Search over natural language content where users express intent in varied ways
- Question-answering over document corpora (RAG retrieval)
- Finding similar items — similar products, duplicate tickets, related articles
- Any use case where keyword search returns poor results due to vocabulary mismatch

## When Not to Apply
- Searches for exact identifiers, codes, or structured data — semantic search is worse than exact matching here
- Very small corpora where a simple `ILIKE` query is sufficient
- When query latency requirements cannot accommodate embedding + ANN lookup overhead

## Key Concepts
- **Query Embedding**: The user's search query is embedded using the same model used to embed the documents — producing a vector that can be compared to document vectors
- **Cosine Similarity Search**: Find the top-k document vectors with highest cosine similarity to the query vector — the semantic search result set
- **Hybrid Search**: Combining semantic search with keyword/BM25 search via Reciprocal Rank Fusion (RRF) or weighted scoring. Captures both conceptual matches (semantic) and exact term matches (keyword). Outperforms either alone for most real-world search tasks
- **BM25**: The dominant keyword search algorithm — scores documents by term frequency and inverse document frequency. Fast, no ML required, excellent for exact term matching
- **Reciprocal Rank Fusion (RRF)**: A rank fusion algorithm that combines results from multiple retrieval methods without requiring score normalization — `score = Σ 1/(k + rank_i)`. Simple and effective
- **Re-ranking**: A cross-encoder model that re-scores the top-k retrieved results for final ordering. More accurate than embedding similarity alone; adds latency
- **Query Expansion**: Augmenting the user's query with related terms or a generated hypothetical answer before embedding — improves recall for short or ambiguous queries
- **HyDE (Hypothetical Document Embeddings)**: Generate a hypothetical answer to the query, embed that answer, and search with it — often better than embedding the raw query for asymmetric retrieval tasks
- **Chunking Strategy Impact**: Search quality depends heavily on how documents were chunked — misaligned chunk boundaries break semantic coherence and reduce retrieval precision

## In Practice
Method semantic search implementations use hybrid search (OpenAI embeddings + PostgreSQL full-text or Elasticsearch BM25) with RRF fusion. Re-ranking is added when precision matters more than latency. Query expansion is used for short or keyword-heavy queries. Chunking strategy is validated by measuring retrieval recall before building the generation layer.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Semantic Search**: Don't replace keyword search with semantic search — combine them (hybrid search with RRF). Semantic search wins on meaning and vocabulary mismatch; BM25 wins on exact terms and identifiers. Use the same embedding model for queries and documents. For short queries, try HyDE — embed a hypothetical answer instead of the raw query. Add re-ranking for high-precision use cases. Always validate retrieval quality independently: measure recall@k before building the generation layer on top. Poor retrieval = poor answers regardless of the LLM. → `engineering-knowledge-repository/semantic-search.md`

## Related Entries
- [Embeddings](embeddings.md) — semantic search is powered by embedding models
- [Vector Databases](vector-databases.md) — the ANN index that executes semantic search queries
- [Retrieval-Augmented Generation](retrieval-augmented-generation.md) — RAG uses semantic search to retrieve relevant document chunks
- [Caching Strategies](caching-strategies.md) — semantic search results can be cached; see LLM Caching for semantic query caching
