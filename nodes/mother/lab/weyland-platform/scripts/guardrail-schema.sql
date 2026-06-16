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
    actor       TEXT,                          -- B14 read+act: trusted gateway identity (X-Forwarded-Consumer), NULL until gateway
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Migration for a pre-existing table (idempotent): add the actor column if it isn't there yet.
ALTER TABLE guardrail_verdicts ADD COLUMN IF NOT EXISTS actor TEXT;
CREATE INDEX IF NOT EXISTS idx_guardrail_verdicts_validator ON guardrail_verdicts(validator, created_at);
CREATE INDEX IF NOT EXISTS idx_guardrail_verdicts_request   ON guardrail_verdicts(request_id);
