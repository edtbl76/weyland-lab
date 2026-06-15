-- B14 guardrail telemetry. Reuses weyland-postgres (DB: weyland). Idempotent.
-- Apply: kubectl exec -i -n weyland deploy/weyland-postgres -- psql -U weyland -d weyland < guardrail-schema.sql
CREATE TABLE IF NOT EXISTS guardrail_verdicts (
    id          BIGSERIAL PRIMARY KEY,
    request_id  TEXT NOT NULL,
    hook        TEXT NOT NULL,                 -- input | output | act
    validator   TEXT NOT NULL,
    mode        TEXT NOT NULL,                 -- off | shadow | flag | block
    decision    TEXT NOT NULL,                 -- pass | flag | block
    score       DOUBLE PRECISION,
    reason      TEXT,
    latency_ms  INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_guardrail_verdicts_validator ON guardrail_verdicts(validator, created_at);
CREATE INDEX IF NOT EXISTS idx_guardrail_verdicts_request   ON guardrail_verdicts(request_id);
