# Flow: Evaluation Pipeline (single-path eval -> panel -> leaderboard)

```mermaid
sequenceDiagram
    participant C as Client (curl /evals)
    participant TS as tool-server /evals
    participant Dag as Dagster eval jobs
    participant RAG as tool-server /context/ask
    participant OLL as Ollama (models + judges)
    participant GQ as golden_questions.json
    participant PG as Postgres eval_*
    C->>TS: POST /evals/run
    TS->>Dag: launch weyland_eval_job
    alt EVAL_QUESTION_SOURCE=golden (default)
        Dag->>GQ: load pinned 20q (10 conceptual + 10 lexical)
    else EVAL_QUESTION_SOURCE=generated
        Dag->>OLL: generate question set
    end
    Dag->>PG: eval_questions (question_type = golden-conceptual / golden-lexical)
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

**Why the `alt` matters (B96):** generated-per-run questions made the leaderboard **non-comparable across runs** —
each run was a different exam, so score deltas measured question difficulty, not system quality. `golden` is the
default; `generated` is kept because a static exam can be overfit to. The `question_type` written here is what lets
the leaderboard be **sliced** conceptual-vs-lexical, which is how retrieval changes are actually evaluated.
See [runbooks/eval-harness.md](../runbooks/eval-harness.md).
