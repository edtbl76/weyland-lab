# Flow: Agentic RAG (`weyland-agent`, B70)

The self-reflective loop — **retrieve → grade → reflect/re-retrieve → generate** — bounded by `max_attempts` (default
2). LangGraph owns the control flow; 4 custom LlamaIndex retrievers do the fetching (in-process bge query embedding);
a LangChain `ChatOpenAI` → Ollama does grade/reflect/generate. Guards the outer query + final answer via the shared
`weyland-guard` service (fail-open). Every LLM + retrieval step is captured by MLflow's langchain + llama_index
autolog → one per-query Trace in the `agentic-rag` experiment. See [demos/agentic-rag.md](../demos/agentic-rag.md) +
[runbooks/agentic-rag.md](../runbooks/agentic-rag.md).

```mermaid
sequenceDiagram
    participant C as Client
    participant A as weyland-agent (LangGraph)
    participant G as weyland-guard
    participant R as LlamaIndex retriever
    participant L as Ollama (ChatOpenAI)
    participant M as MLflow
    C->>A: POST /agent/ask {query, backend, max_attempts}
    A->>G: POST /guard/input (fail-open)
    A->>R: retrieve(backend, query)
    R-->>A: chunks (top-k)
    A->>L: grade — do chunks answer the question? (YES/NO)
    alt weak AND attempts < max_attempts
        A->>L: reflect — rewrite query / switch backend
        Note over A: attempts += 1
        A->>R: retrieve(new backend, new query)
        R-->>A: chunks
    end
    A->>L: generate — grounded answer over the chunks
    A->>G: POST /guard/output (answer, sources — fail-open)
    A->>M: autolog Trace — retrieve / grade / reflect / generate spans
    A-->>C: {answer, sources, attempts, backend_used, backend_history}
```
