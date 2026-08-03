# Flow: Eval Scoring (`weyland_eval_score_job`, detail of the eval pipeline)

The second half of evaluation — judges the latest run's results with an LLM panel. Distinct from generation
(`weyland_eval_job` = `eval_testset` + `eval_run_matrix`); see [flow-eval.md](flow-eval.md) for the run side.
Triggerable via `/evals/score` (an audited act-tool — see [flow-act-tool.md](flow-act-tool.md)). The
`eval_leaderboard` is a **view** that averages across judges on read — the job never refreshes or materializes
it. Since **B115** each judge's raw JSON passes through the **`guardrails-structure`** service (the platform's
Structure layer) — validated against the `JudgeScores` schema and re-asked to repair on a miss — before it's written
(fail-safe: a best-effort parse if the service is down). See [runbooks/guardrails.md](../runbooks/guardrails.md).

```mermaid
sequenceDiagram
    participant C as Client (/evals/score)
    participant TS as tool-server /evals/score
    participant Dag as Dagster weyland_eval_score_job (eval_scores asset)
    participant OLL as Ollama (judge panel, >=3 models)
    participant GS as guardrails-structure (Structure guard)
    participant PG as Postgres eval_*
    C->>TS: POST /evals/score
    TS->>Dag: launch weyland_eval_score_job
    Dag->>PG: select latest run (eval_runs) + its eval_results x eval_questions, per-judge unscored
    Dag->>OLL: judge each result (panel scoring via /chat/completions)
    OLL-->>Dag: raw scores JSON
    Dag->>GS: POST /structure/judge-scores {raw, model} (B115 — validate JudgeScores)
    GS->>OLL: re-ask the judge to repair on a schema miss
    OLL-->>GS: repaired JSON
    GS-->>Dag: validated scores (guarded | reasked)
    Note over Dag,GS: fail-open — GS unreachable => Dag best-effort parses the raw
    Dag->>PG: write eval_scores
    Dag->>PG: UPDATE eval_runs SET status='scored'
    Note over PG: eval_leaderboard is a VIEW (avg across judges) — read on demand, never refreshed here
```
