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
    out = es.resolve_run_settings("neo4j", ["qwen3:30b-a3b"], 6, DEFAULTS)
    assert out == {"backend": "neo4j", "models": ["qwen3:30b-a3b"], "ask_limit": 6}


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


def test_valid_backends_are_the_four_stores():
    # B247 (2026-11-13): the measured experimental retrieval modes are retired; the tool server serves the four stores.
    assert es.VALID_BACKENDS == {"pgvector", "qdrant", "weaviate", "neo4j"}


def test_a_retired_mode_fails_before_the_run():
    with pytest.raises(ValueError, match="unknown eval backend"):
        es.resolve_run_settings("neo4j_graph_rerank", None, None, DEFAULTS)


# --- question_set: which pinned exam a run takes (B38 Phase 0 follow-up) -------------------------------------------

def test_question_set_defaults_to_golden(tmp_path):
    (tmp_path / "golden.json").write_text("{}")
    assert es.question_set_path("", str(tmp_path)) == str(tmp_path / "golden.json")
    assert es.question_set_path(None, str(tmp_path)) == str(tmp_path / "golden.json")


def test_question_set_named_file(tmp_path):
    (tmp_path / "multi_entity.json").write_text("{}")
    assert es.question_set_path("multi_entity", str(tmp_path)) == str(tmp_path / "multi_entity.json")


def test_question_set_missing_file_fails(tmp_path):
    with pytest.raises(ValueError, match="no question set"):
        es.question_set_path("nope", str(tmp_path))


@pytest.mark.parametrize("name", ["../secrets", "a/b", "x.json", "UPPER", "with space"])
def test_question_set_name_must_be_a_plain_name(tmp_path, name):
    with pytest.raises(ValueError, match="question set name"):
        es.question_set_path(name, str(tmp_path))
