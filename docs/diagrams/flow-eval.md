# Flow: Evaluation Pipeline (single-path eval -> panel -> leaderboard)

```mermaid
sequenceDiagram
    participant C as Client (curl /evals)
    participant TS as tool-server /evals
    participant Dag as Dagster eval jobs
    participant RAG as tool-server /context/ask
    participant OLL as Ollama (models + judges)
    participant PG as Postgres eval_*
    C->>TS: POST /evals/run
    TS->>Dag: launch weyland_eval_job
    Dag->>OLL: generate question set
    Dag->>PG: eval_questions
    loop each question x 6 models
        Dag->>RAG: /context/ask (model)
        RAG->>OLL: generate
        Dag->>PG: eval_results
    end
    C->>TS: POST /evals/score
    TS->>Dag: launch weyland_eval_score_job
    loop each result x 3 judges
        Dag->>OLL: judge (faithfulness / relevancy)
        Dag->>PG: eval_scores
    end
    C->>TS: GET /evals/leaderboard
    TS->>PG: panel-average query
    TS-->>C: leaderboard
```

**B4 finding:** `gpt-oss:20b` is the most defensible RAG model (stable rank across configs; single-judge scoring proven noisy -> 3-judge panel).
