-- B4 — LLM evaluation pipeline schema.
-- Reuses weyland-postgres (DB: weyland), alongside the existing rag_* tables. No new DB.
-- Apply: kubectl exec -i -n weyland deploy/weyland-postgres -- psql -U weyland -d weyland < eval-schema.sql
-- Idempotent (IF NOT EXISTS / OR REPLACE) so it's safe to re-run.

-- One row per leaderboard execution.
CREATE TABLE IF NOT EXISTS eval_runs (
    id             BIGSERIAL PRIMARY KEY,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    status         TEXT NOT NULL DEFAULT 'running',   -- running | complete | failed
    models         TEXT[] NOT NULL,                   -- model tags evaluated this run
    metrics        TEXT[] NOT NULL,                   -- ragas metrics applied
    question_count INTEGER,
    notes          TEXT
);

-- Ragas-generated questions for a run (auto-gen from the rag_* corpus).
CREATE TABLE IF NOT EXISTS eval_questions (
    id                 BIGSERIAL PRIMARY KEY,
    run_id             BIGINT NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    question           TEXT NOT NULL,
    question_type      TEXT,                          -- ragas evolution: simple / reasoning / multi_context
    reference_answer   TEXT,                          -- nullable (ragas may synthesize one)
    reference_contexts JSONB,                         -- nullable (ground-truth chunks, if generated)
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One RAG output per (question x model): the answer + the chunks it was grounded on.
CREATE TABLE IF NOT EXISTS eval_results (
    id          BIGSERIAL PRIMARY KEY,
    run_id      BIGINT NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    question_id BIGINT NOT NULL REFERENCES eval_questions(id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    backend     TEXT NOT NULL DEFAULT 'pgvector',     -- vector backend used for retrieval
    answer      TEXT,
    contexts    JSONB,                                -- retrieved chunks (the grounding set)
    latency_ms  INTEGER,
    error       TEXT,                                 -- set if the /context/ask call failed
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- LLM-as-judge metric scores per result, per JUDGE (panel). Narrow table = add metrics/judges
-- without schema changes; the eval_leaderboard view averages across judges.
CREATE TABLE IF NOT EXISTS eval_scores (
    id         BIGSERIAL PRIMARY KEY,
    result_id  BIGINT NOT NULL REFERENCES eval_results(id) ON DELETE CASCADE,
    metric     TEXT NOT NULL,                         -- faithfulness | answer_relevancy | context_relevancy
    judge      TEXT NOT NULL,                         -- judge model (panel: ≥3 judges per result/metric)
    score      DOUBLE PRECISION,                      -- nullable if scoring failed
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (result_id, metric, judge)
);

-- Leaderboard: average metric score per (run, model). A view stays always-current — the
-- tool-server's GET /evals/leaderboard reads this directly.
CREATE OR REPLACE VIEW eval_leaderboard AS
SELECT
    res.run_id,
    res.model,
    sc.metric,
    AVG(sc.score)   AS avg_score,
    COUNT(sc.score) AS scored_n
FROM eval_results res
JOIN eval_scores  sc ON sc.result_id = res.id
GROUP BY res.run_id, res.model, sc.metric;

CREATE INDEX IF NOT EXISTS idx_eval_results_run   ON eval_results(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_model ON eval_results(run_id, model);
CREATE INDEX IF NOT EXISTS idx_eval_scores_result ON eval_scores(result_id);
