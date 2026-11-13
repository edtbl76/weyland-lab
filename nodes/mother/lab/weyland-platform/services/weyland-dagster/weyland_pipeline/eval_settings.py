"""Per-run settings of the RAG eval (B38, 2026-11-12) — pure, no dagster import, so it is unit-testable as is.

The retrieval backend, the answer models and the context depth (`ask_limit`) used to be deployment env vars
(EVAL_BACKEND / EVAL_MODELS / EVAL_ASK_LIMIT): comparing two backends meant a manifest change and a pod restart per
run. eval_testset now takes them as run config; an empty value keeps the env default, so a run launched with no
config behaves exactly as before. A run that could not measure anything fails here, before it starts.
"""
import os
import re

# The tool-server's search backends (weyland-tool-server main.py SEARCH_FNS). The two neo4j_graph_* modes are B38
# Phase 0: graph-aware retrieval over the B37 frontmatter graph, measured against plain `neo4j`.
VALID_BACKENDS = {"pgvector", "qdrant", "weaviate", "neo4j", "neo4j_graph_rerank", "neo4j_graph_expand",
                  "neo4j_decompose_rule", "neo4j_decompose_llm",  # B247: query decomposition
                  "neo4j_decompose_ctx", "neo4j_adaptive_k"}  # B247 iteration 2


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


_SET_NAME = re.compile(r"^[a-z0-9_-]+$")


def question_set_path(name, sets_dir: str) -> str:
    """The pinned exam a run takes: eval_sets/<name>.json, default "golden". A plain lowercase name only (no path,
    no extension), and the file must exist — a typo fails before the run instead of silently using another exam."""
    name = (name or "").strip() or "golden"
    if not _SET_NAME.match(name):
        raise ValueError(f"question set name must be a plain lowercase name (eval_sets/<name>.json), got {name!r}")
    path = os.path.join(sets_dir, f"{name}.json")
    if not os.path.isfile(path):
        raise ValueError(f"no question set {name!r}: {path} does not exist")
    return path
