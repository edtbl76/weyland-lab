-- model_catalog — the hosted-model lookup table (refreshed by the Dagster `model_catalog` asset, 6h).
-- A flat current-state snapshot (replace-by-source each run), distinct from the normalized infra
-- `models` inventory table (model -> service -> machine). This is "what models can I reach", that is
-- "which of my services serves which model". The asset also runs this DDL (CREATE IF NOT EXISTS), so
-- applying this file by hand is optional — it's the tracked source of truth for the schema.
CREATE TABLE IF NOT EXISTS model_catalog (
    id                 BIGSERIAL PRIMARY KEY,
    source             TEXT NOT NULL,          -- openrouter | gemini | ollama
    model_id           TEXT NOT NULL,          -- id you pass through LiteLLM (e.g. openrouter/deepseek/...:free)
    free               BOOLEAN,                -- true/false; NULL = unknown (e.g. Gemini, free tier is account-level)
    context_length     INTEGER,
    pricing_prompt     NUMERIC,                -- as reported by the provider (USD/token); NULL if unknown
    pricing_completion NUMERIC,
    metadata           JSONB NOT NULL DEFAULT '{}',
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, model_id)
);
CREATE INDEX IF NOT EXISTS idx_model_catalog_source ON model_catalog (source);
CREATE INDEX IF NOT EXISTS idx_model_catalog_free   ON model_catalog (free);
