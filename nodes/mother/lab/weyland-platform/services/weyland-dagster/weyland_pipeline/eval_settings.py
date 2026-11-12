"""Per-run settings of the RAG eval (B38, 2026-11-12) — pure, no dagster import, so it is unit-testable as is.

The retrieval backend, the answer models and the context depth (`ask_limit`) used to be deployment env vars
(EVAL_BACKEND / EVAL_MODELS / EVAL_ASK_LIMIT): comparing two backends meant a manifest change and a pod restart per
run. eval_testset now takes them as run config; an empty value keeps the env default, so a run launched with no
config behaves exactly as before. A run that could not measure anything fails here, before it starts.
"""

# The tool-server's search backends (weyland-tool-server main.py SEARCH_FNS). The two neo4j_graph_* modes are B38
# Phase 0: graph-aware retrieval over the B37 frontmatter graph, measured against plain `neo4j`.
VALID_BACKENDS = {"pgvector", "qdrant", "weaviate", "neo4j", "neo4j_graph_rerank", "neo4j_graph_expand"}


def resolve_run_settings(backend, models, ask_limit, defaults: dict) -> dict:
    """Settings for one eval run: each value given wins, an empty one (None / "" / [] / 0) falls back to `defaults`
    (the env values). Raises ValueError for a run that would measure nothing."""
    out_backend = (backend or "").strip() or defaults["backend"]
    if out_backend not in VALID_BACKENDS:
        raise ValueError(f"unknown eval backend {out_backend!r}; expected one of {sorted(VALID_BACKENDS)}")

    given = [m.strip() for m in (models or []) if m and m.strip()]
    out_models = given or [m.strip() for m in defaults["models"] if m and m.strip()]
    if not out_models:
        raise ValueError("no eval models: give `models` in the run config or set EVAL_MODELS")

    if ask_limit is not None and ask_limit < 0:
        raise ValueError(f"ask_limit must be >= 1 (0 = default), got {ask_limit}")
    out_limit = ask_limit or defaults["ask_limit"]
    return {"backend": out_backend, "models": out_models, "ask_limit": out_limit}
