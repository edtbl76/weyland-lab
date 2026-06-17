"""Hosted-model catalog — keeps the `model_catalog` table fresh (6h schedule, group "catalog").

Pulls the model menus we can reach and lands them as a flat current-state lookup table:
  - OpenRouter  -> GET /api/v1/models (public, no key) — id, pricing, context; free = both prices "0"
  - Gemini      -> GET /v1beta/models?key=... — needs GEMINI_API_KEY (else source skipped, resilient)
  - Ollama      -> GET /api/tags (local, $0)

Each source is independent: one failing (rate limit, no key) logs a warning and the others still write.
Write is **replace-by-source** (DELETE WHERE source=X, then INSERT) so the table never accumulates — same
snapshot semantics as the vector ingestion's orphan pruning. Distinct from the normalized `models` infra
inventory table; see scripts/model-catalog-schema.sql.
"""
import json
import os

import httpx
from dagster import asset, Output, MetadataValue

from weyland_pipeline.resources import PostgresResource

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.244:11434/v1")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DDL = """
CREATE TABLE IF NOT EXISTS model_catalog (
    id                 BIGSERIAL PRIMARY KEY,
    source             TEXT NOT NULL,
    model_id           TEXT NOT NULL,
    free               BOOLEAN,
    context_length     INTEGER,
    pricing_prompt     NUMERIC,
    pricing_completion NUMERIC,
    metadata           JSONB NOT NULL DEFAULT '{}',
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, model_id)
);
CREATE INDEX IF NOT EXISTS idx_model_catalog_source ON model_catalog (source);
CREATE INDEX IF NOT EXISTS idx_model_catalog_free   ON model_catalog (free);
"""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_zero(v) -> bool:
    return _num(v) == 0.0


def _openrouter() -> list[dict]:
    resp = httpx.get(OPENROUTER_MODELS_URL, timeout=30)
    resp.raise_for_status()
    rows = []
    for m in resp.json().get("data", []):
        pricing = m.get("pricing") or {}
        p, c = pricing.get("prompt"), pricing.get("completion")
        rows.append({
            "source": "openrouter",
            "model_id": m.get("id"),
            "free": _is_zero(p) and _is_zero(c),
            "context_length": m.get("context_length"),
            "pricing_prompt": _num(p),
            "pricing_completion": _num(c),
            "metadata": {"name": m.get("name"), "top_provider": m.get("top_provider")},
        })
    return rows


def _gemini() -> list[dict]:
    if not GEMINI_API_KEY:
        return []  # source skipped — wire GEMINI_API_KEY into the Dagster deployment to enable
    resp = httpx.get(GEMINI_MODELS_URL, params={"key": GEMINI_API_KEY, "pageSize": 1000}, timeout=30)
    resp.raise_for_status()
    rows = []
    for m in resp.json().get("models", []):
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue  # skip embedding/other non-chat models
        rows.append({
            "source": "gemini",
            "model_id": m["name"].replace("models/", "gemini/"),  # matches LiteLLM gemini/<id>
            "free": None,  # Gemini's free tier is account-level, not per-model
            "context_length": m.get("inputTokenLimit"),
            "pricing_prompt": None,
            "pricing_completion": None,
            "metadata": {"display_name": m.get("displayName")},
        })
    return rows


def _ollama() -> list[dict]:
    base = OLLAMA_BASE_URL.replace("/v1", "")  # /api/tags is the native list
    resp = httpx.get(f"{base}/api/tags", timeout=15)
    resp.raise_for_status()
    return [{
        "source": "ollama",
        "model_id": f"ollama/{m['name']}",
        "free": True,  # local box, $0
        "context_length": None,
        "pricing_prompt": 0,
        "pricing_completion": 0,
        "metadata": {"family": (m.get("details") or {}).get("family")},
    } for m in resp.json().get("models", [])]


@asset(group_name="catalog")
def model_catalog(context, postgres: PostgresResource) -> Output[dict]:
    sources = {"openrouter": _openrouter, "gemini": _gemini, "ollama": _ollama}
    collected: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}
    for name, fetch in sources.items():
        try:
            collected[name] = fetch()
        except Exception as exc:  # one source's failure must not sink the others
            errors[name] = str(exc)
            context.log.warning(f"model_catalog: source '{name}' failed: {exc}")

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            for name, rows in collected.items():
                cur.execute("DELETE FROM model_catalog WHERE source = %s", (name,))
                for r in rows:
                    cur.execute(
                        """
                        INSERT INTO model_catalog
                          (source, model_id, free, context_length, pricing_prompt, pricing_completion, metadata, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (source, model_id) DO UPDATE SET
                          free = EXCLUDED.free, context_length = EXCLUDED.context_length,
                          pricing_prompt = EXCLUDED.pricing_prompt, pricing_completion = EXCLUDED.pricing_completion,
                          metadata = EXCLUDED.metadata, updated_at = now()
                        """,
                        (r["source"], r["model_id"], r["free"], r["context_length"],
                         r["pricing_prompt"], r["pricing_completion"], json.dumps(r["metadata"])),
                    )
        conn.commit()

    counts = {k: len(v) for k, v in collected.items()}
    free_counts = {k: sum(1 for r in v if r.get("free")) for k, v in collected.items()}
    context.log.info(f"model_catalog written: counts={counts} free={free_counts} errors={list(errors)}")
    return Output(
        {"counts": counts, "free": free_counts, "errors": errors},
        metadata={
            "openrouter_total": counts.get("openrouter", 0),
            "openrouter_free": free_counts.get("openrouter", 0),
            "gemini_total": counts.get("gemini", 0),
            "ollama_total": counts.get("ollama", 0),
            "errors": MetadataValue.json(errors),
        },
    )
