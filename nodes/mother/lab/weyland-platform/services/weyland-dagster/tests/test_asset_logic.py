"""Tests for the pure decision logic inside two dagster asset modules — the parts that DO branch (maxcc 15-16),
loaded in isolation with dagster + the resource/httpx edges stubbed (the assets themselves run in the pipeline).

  * source_document — what counts as an ingestable source doc: the exclusion rules (secrets/binaries/vendored
    dirs) and the markdown/code classification. A wrong rule silently ingests a `.env` into the KB, or drops
    real docs. Pure except `_has_shebang` (a 2-byte file read, exercised via tmp files).
  * eval_testset._extract_questions — pulls a question list out of a messy LLM reply (qwen `<think>` blocks,
    JSON object/array, or a bare question-per-line fallback). If it mis-parses, the eval set is empty or garbage.
"""
import importlib.util
import os
import sys
import types

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # weyland-dagster/


def _stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _Subscriptable:  # dagster's Output is used as Output[dict] in annotations at module scope
    def __class_getitem__(cls, item):
        return cls


# dagster + the resource/httpx edges these two modules import at module scope (never called by these tests).
_stub("dagster", asset=lambda *a, **k: (a[0] if a and callable(a[0]) and not k else (lambda f: f)),
      RetryPolicy=lambda *a, **k: None, get_dagster_logger=lambda *a, **k: None,
      Output=_Subscriptable, MetadataValue=type("MV", (), {"__getattr__": lambda s, n: (lambda *a, **k: None)})())
_stub("httpx")
_wp = _stub("weyland_pipeline"); _wp.__path__ = [_ROOT + "/weyland_pipeline"]
_stub("weyland_pipeline.resources", PostgresResource=type("PostgresResource", (), {}))


def _load(relpath, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, "weyland_pipeline", relpath))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def sd():
    return _load("assets/source_document.py", "sd_isolated")


@pytest.fixture(scope="module")
def ets():
    return _load("assets/eval_testset.py", "ets_isolated")


# ── source_document: exclusion rules ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path", [
    "nodes/x/secret.env", "nodes/x/tls.key", "nodes/x/cert.pem", "poetry.lock",
    "docs/diagram.png", "nodes/encryption-key-note.md", "nodes/x/my-secret-thing.yaml",
    "nodes/x/node_modules/pkg/index.js", "nodes/x/__pycache__/m.pyc", "nodes/openclaw/lab/whatever.py",
])
def test_is_excluded_true_for_secrets_binaries_vendored_and_openclaw(sd, path):
    assert sd._is_excluded(path) is True


@pytest.mark.parametrize("path", ["docs/guide.md", "nodes/mother/app.py", "nodes/x/deploy.yaml"])
def test_is_excluded_false_for_normal_source(sd, path):
    assert sd._is_excluded(path) is False


# ── source_document: shebang + classification ────────────────────────────────────────────────────────
def test_has_shebang(sd, tmp_path):
    yes = tmp_path / "run"; yes.write_bytes(b"#!/bin/sh\necho hi")
    no = tmp_path / "plain"; no.write_bytes(b"echo hi")
    assert sd._has_shebang(str(yes)) is True
    assert sd._has_shebang(str(no)) is False
    assert sd._has_shebang(str(tmp_path / "missing")) is False   # OSError → False, never raises


def test_included_kind_markdown_and_code(sd):
    assert sd._included_kind("docs/guide.md", "/x") == "markdown"      # docs tree markdown
    assert sd._included_kind("nodes/a/readme.md", "/x") == "markdown"  # nodes tree markdown
    assert sd._included_kind("nodes/a/app.py", "/x") == "code"         # code extension
    assert sd._included_kind("nodes/a/Dockerfile", "/x") == "code"     # exact basename
    assert sd._included_kind("nodes/a/deploy.yaml", "/x") == "code"


def test_included_kind_excludes_docs_outside_docs_and_non_nodes(sd):
    assert sd._included_kind("README.md", "/x") is None               # top-level md, not docs/ or nodes/
    assert sd._included_kind("nodes/a/data.txt", "/x") is None         # under nodes/ but not a code ext
    assert sd._included_kind("other/a/app.py", "/x") is None           # not under nodes/


def test_included_kind_extensionless_bin_shebang_is_code(sd, tmp_path):
    script = tmp_path / "tool"; script.write_bytes(b"#!/usr/bin/env python\n")
    assert sd._included_kind("nodes/a/bin/tool", str(script)) == "code"
    plain = tmp_path / "plain"; plain.write_bytes(b"nope")
    assert sd._included_kind("nodes/a/bin/plain", str(plain)) is None   # no shebang → not code


# ── eval_testset._extract_questions: the messy-reply parser ──────────────────────────────────────────
def test_extract_questions_json_object(ets):
    assert ets._extract_questions('{"questions": ["Q1?", "Q2?"]}', 5) == ["Q1?", "Q2?"]


def test_extract_questions_strips_think_block(ets):
    out = ets._extract_questions('<think>reasoning noise</think>{"questions": ["Real?"]}', 5)
    assert out == ["Real?"]


def test_extract_questions_json_array(ets):
    assert ets._extract_questions('["A?", "B?", "C?"]', 5) == ["A?", "B?", "C?"]


def test_extract_questions_respects_limit_n(ets):
    assert ets._extract_questions('["A?","B?","C?","D?"]', 2) == ["A?", "B?"]


def test_extract_questions_dict_without_questions_key_uses_first_list(ets):
    assert ets._extract_questions('{"items": ["X?", "Y?"]}', 5) == ["X?", "Y?"]


def test_extract_questions_line_fallback_strips_markers(ets):
    content = "Here are some:\n1. What is X?\n- How does Y work?\nnot a question\n* Why Z?"
    assert ets._extract_questions(content, 5) == ["What is X?", "How does Y work?", "Why Z?"]


def test_extract_questions_empty_when_nothing_parseable(ets):
    assert ets._extract_questions("just prose with no questions", 5) == []
