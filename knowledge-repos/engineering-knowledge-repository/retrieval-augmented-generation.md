---
id: retrieval-augmented-generation
tags: [pattern, ai-ml, backend, distributed-systems]
surfaces-at: [application-design, functional-design, infrastructure-design]
related: [embeddings, vector-databases, semantic-search, prompt-engineering, fine-tuning-vs-rag, context-window-management, llm-evaluation]
complexity: intermediate
---

# Retrieval-Augmented Generation (RAG)

## What It Is
An architecture that grounds LLM responses in retrieved documents rather than relying solely on the model's parametric knowledge. When a query arrives, relevant documents are retrieved from a knowledge base (typically via semantic search over a vector store), injected into the prompt as context, and the LLM generates a response grounded in that context. RAG reduces hallucination, enables knowledge to be updated without retraining, and allows the model to cite sources.

## When to Apply
- LLM applications that need to answer questions about proprietary or frequently-updated knowledge (documentation, policies, product catalogs)
- When hallucination risk is unacceptable and grounding responses in real documents is required
- When the knowledge base changes frequently — RAG updates are instant (re-index); fine-tuning requires retraining
- As the default architecture before considering fine-tuning for knowledge-intensive tasks

## When Not to Apply
- Tasks requiring reasoning style or tone adaptation rather than knowledge injection — fine-tuning is better
- Very low-latency requirements where the retrieval step adds unacceptable overhead
- Highly structured output tasks where the format, not the knowledge, is the hard problem

## Key Concepts
- **Chunking**: Splitting source documents into segments for indexing. Chunk size is a critical parameter — too small loses context; too large wastes context window. Common strategies: fixed-size with overlap, sentence/paragraph boundaries, semantic chunking
- **Embedding**: Each chunk is converted to a vector representation by an embedding model. Similar chunks produce similar vectors — the basis for semantic retrieval
- **Vector Store**: The index of embedded chunks — queried at runtime to find the chunks most similar to the user's query
- **Retrieval**: At query time, the query is embedded and the top-k most similar chunks are retrieved. k is a tunable parameter — more chunks = more context, higher cost, possible dilution
- **Augmented Prompt**: Retrieved chunks are injected into the prompt: `"Answer using only the following context: [chunks]. Question: [query]"`
- **Re-ranking**: A second-pass model (cross-encoder) re-scores retrieved chunks for relevance before injecting. Improves precision at the cost of latency
- **Hybrid Search**: Combining semantic (vector) search with keyword (BM25) search — captures both semantic similarity and exact term matches. Often outperforms either alone
- **RAG Evaluation**: Faithfulness (does the answer match the context?), answer relevance (does it answer the question?), context relevance (were the right chunks retrieved?)
- **Naive vs. Advanced RAG**: Naive RAG = embed, store, retrieve, generate. Advanced RAG adds query rewriting, re-ranking, hybrid search, and iterative retrieval

## In Practice
Method RAG implementations use OpenAI embeddings (or equivalent) for chunking and retrieval, pgvector or Pinecone as the vector store, hybrid search for better recall, and re-ranking for precision. Chunk size is validated empirically. Retrieval quality is evaluated before generation quality — garbage in, garbage out. RAG pipelines are instrumented with LLM observability tooling to trace chunk retrieval and generation.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — RAG**: Ground LLM responses in retrieved documents to reduce hallucination and enable updatable knowledge. The pipeline: chunk → embed → store → retrieve → augment prompt → generate. Chunking strategy matters — test chunk sizes empirically. Use hybrid search (semantic + BM25) for better recall. Add re-ranking for precision. Evaluate retrieval quality independently from generation quality — bad retrieval produces bad answers regardless of the LLM. RAG is almost always the right first choice over fine-tuning for knowledge-injection tasks. → `engineering-knowledge-repository/retrieval-augmented-generation.md`

## Related Entries
- [Embeddings](embeddings.md) — chunks are embedded into vectors for semantic retrieval
- [Vector Databases](vector-databases.md) — the storage and retrieval layer for embedded chunks
- [Semantic Search](semantic-search.md) — the retrieval mechanism that finds relevant chunks
- [Prompt Engineering](prompt-engineering.md) — retrieved context is injected into a carefully designed prompt
- [Fine-Tuning vs. RAG](fine-tuning-vs-rag.md) — decision framework for when RAG is sufficient vs. fine-tuning is needed
- [Context Window Management](context-window-management.md) — retrieved chunks consume context window space
- [LLM Evaluation](llm-evaluation.md) — RAG systems require evaluation of retrieval and generation quality
