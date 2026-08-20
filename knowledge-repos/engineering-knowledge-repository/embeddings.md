---
id: embeddings
tags: [pattern, ai-ml, backend]
surfaces-at: [application-design, functional-design]
related: [vector-databases, semantic-search, retrieval-augmented-generation, fine-tuning-vs-rag]
complexity: intermediate
---

# Embeddings

## What It Is
Dense vector representations of data (text, images, audio) where semantic similarity is encoded as geometric proximity. An embedding model maps input to a point in high-dimensional space such that similar inputs land near each other. "The Eiffel Tower is in Paris" and "France's most famous landmark is in its capital" produce vectors close together; "banana" produces a vector far away. Embeddings are the foundation of semantic search, RAG, recommendation systems, and clustering.

## When to Apply
- Any task requiring semantic similarity rather than exact matching — search, deduplication, recommendations, clustering
- RAG pipelines — documents are embedded for retrieval
- Classification and anomaly detection where a vector representation is more expressive than raw features

## Key Concepts
- **Embedding Model**: The neural network that converts input to vector. Choice matters — different models optimize for different domains (code, multilingual, long documents). Common: OpenAI `text-embedding-3-large`, Cohere Embed, Sentence Transformers (open source)
- **Dimensionality**: The length of the output vector — typically 768 to 3072 dimensions. Higher dimensions = more expressive but higher storage and compute cost. `text-embedding-3-small` (1536) vs `text-embedding-3-large` (3072)
- **Cosine Similarity**: The most common similarity metric — measures the angle between vectors, range -1 to 1. Dot product is equivalent when vectors are normalized (and faster to compute)
- **Semantic vs. Lexical Similarity**: Embeddings capture meaning; keyword matching captures exact terms. "car" and "automobile" are semantically similar but lexically different — embeddings find the relationship; BM25 does not
- **Chunking Before Embedding**: Long documents must be split into chunks before embedding — most models have token limits (512–8192 tokens). Embedding quality degrades for inputs exceeding the model's context
- **Matryoshka Representation Learning (MRL)**: Embeddings where leading dimensions already form a lower-dimensional embedding — enables variable-dimension truncation without full re-embedding. Supported by OpenAI `text-embedding-3-*` models
- **Domain-Specific Embeddings**: General-purpose embeddings underperform on specialized domains (medical, legal, code). Fine-tuning or choosing a domain-specific model improves retrieval quality
- **Embedding Drift**: The same text embedded with different model versions produces different vectors — incompatible for retrieval. Re-embedding all content is required when changing models
- **Batch Embedding**: Embed in batches for throughput — most APIs support batch input. Avoid embedding one document at a time in bulk pipelines

## In Practice
Method uses OpenAI `text-embedding-3-small` for cost-effective general-purpose tasks and `text-embedding-3-large` for quality-critical retrieval. Embeddings are stored in pgvector for small-to-medium corpora and Pinecone for large-scale or multi-tenant use cases. Embedding model version is pinned and documented — changing it requires re-embedding all content.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Embeddings**: Embeddings convert text (or other data) into vectors where semantic similarity = geometric proximity. The model choice matters — test retrieval quality, not just benchmark scores. Chunk before embedding; most models degrade beyond their context limit. Pin your embedding model version — changing models requires re-embedding everything. Use cosine similarity or dot product (on normalized vectors). For multilingual or domain-specific use cases, evaluate specialized models over general-purpose ones. Batch your embedding calls in pipelines — one-at-a-time is slow and expensive. → `engineering-knowledge-repository/embeddings.md`

## Related Entries
- [Vector Databases](vector-databases.md) — the storage and retrieval system for embedding vectors
- [Semantic Search](semantic-search.md) — embeddings enable semantic search over document corpora
- [Retrieval-Augmented Generation](retrieval-augmented-generation.md) — RAG pipelines depend on embeddings for chunk retrieval
- [Fine-Tuning vs. RAG](fine-tuning-vs-rag.md) — embeddings-based RAG is the primary alternative to fine-tuning for knowledge injection
