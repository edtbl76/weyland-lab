"""Tests for eval_settings.resolve_run_settings — the per-run settings of the RAG eval (B38, 2026-11-12).

The eval's retrieval backend, answer models and context depth used to be deployment env vars, so comparing two
backends meant a manifest change and a restart per run. They are now per-run (Dagster run config on eval_testset),
with the env values as defaults. These pin the decisions: empty config means today's behaviour, a value given wins,
and a run that could not measure anything (unknown backend, no models, depth < 1) fails before it starts rather
than producing a leaderboard of errors.
"""
import importlib.util
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("eval_settings", os.path.join(_ROOT, "weyland_pipeline", "eval_settings.py"))
es = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(es)

DEFAULTS = {"backend": "pgvector", "models": ["qwen3:30b-a3b", "gpt-oss:20b"], "ask_limit": 3}


def test_empty_config_keeps_the_env_defaults():
    assert es.resolve_run_settings(None, None, None, DEFAULTS) == DEFAULTS
    assert es.resolve_run_settings("", [], 0, DEFAULTS) == DEFAULTS


def test_given_values_win():
    out = es.resolve_run_settings("neo4j_graph_rerank", ["qwen3:30b-a3b"], 6, DEFAULTS)
    assert out == {"backend": "neo4j_graph_rerank", "models": ["qwen3:30b-a3b"], "ask_limit": 6}


def test_models_are_trimmed_and_blank_entries_dropped():
    out = es.resolve_run_settings(None, [" qwen3:14b ", "", "  "], None, DEFAULTS)
    assert out["models"] == ["qwen3:14b"]


@pytest.mark.parametrize("backend", sorted(es.VALID_BACKENDS))
def test_every_tool_server_backend_is_accepted(backend):
    assert es.resolve_run_settings(backend, None, None, DEFAULTS)["backend"] == backend


def test_an_unknown_backend_fails_before_the_run():
    with pytest.raises(ValueError, match="unknown eval backend"):
        es.resolve_run_settings("neo5j", None, None, DEFAULTS)


def test_no_models_at_all_fails():
    with pytest.raises(ValueError, match="no eval models"):
        es.resolve_run_settings(None, None, None, {**DEFAULTS, "models": []})


def test_a_negative_depth_fails():
    with pytest.raises(ValueError, match="ask_limit"):
        es.resolve_run_settings(None, None, -1, DEFAULTS)


def test_valid_backends_include_both_graph_modes():
    assert {"neo4j", "neo4j_graph_rerank", "neo4j_graph_expand"} <= es.VALID_BACKENDS
