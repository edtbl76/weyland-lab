# Flow: Langfuse evaluation — online RAG grading (B103)

Online eval: every `rag-generate` observation is scored live by 9 LLM-as-judge evaluators on Langfuse's own engine
(judge = `wl-judge-oss`, local gpt-oss:20b, $0), no human in the loop. Complements the offline B84 MLflow judge-panel.

```mermaid
sequenceDiagram
    autonumber
    participant U as Caller
    participant T as tool-server /context/ask
    participant LF as Langfuse
    participant W as langfuse-worker
    participant J as wl-judge-oss<br/>(gpt-oss:20b via LiteLLM)
    U->>T: POST /context/ask {query, backend}
    T->>T: retrieve then generate (rag-generate)
    T->>LF: emit trace + rag-generate observation
    T-->>U: answer
    LF->>W: enqueue evaluation rules (async)
    loop 9 evaluators (7 managed + citation + refusal)
        W->>J: judge the observation
        J-->>W: score (numeric / categorical)
        W->>LF: attach score to the trace
    end
    Note over LF: scores queryable at /api/public/v2/scores
```

**Read-only** — grades live production traces. Demo: [demos/langfuse-evaluation.md](../demos/langfuse-evaluation.md).
