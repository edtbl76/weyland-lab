"""Tests for model_lifecycle.py (B223) — fail when a config names an Anthropic model that is deprecated or retired.

The live fixtures use shapes observed 2026-10-19:
  MLflow gateway  GET /api/3.0/mlflow/gateway/model-definitions/list -> {model_definitions: [{name, provider, model_name, …}]}
  Bifrost 2.3.1   GET /api/providers/anthropic/keys -> {keys: [{name, enabled, models, blacklisted_models, …}], total}
                  GET /api/governance/virtual-keys  -> {virtual_keys: [{name, provider_configs: [{provider, allowed_models}]}]}
  Anthropic       GET /v1/models?limit=1000         -> {data: [{id, …}], has_more}
"""
import datetime as dt
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import model_lifecycle as ml  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(os.path.dirname(HERE), "anthropic-models.json")
TODAY = dt.date(2026, 10, 19)


@pytest.fixture(scope="module")
def manifest():
    return ml.load_manifest(MANIFEST_PATH)


# ── parsing: every spelling of one model resolves to the same key ─────────────────────────────────────────────────

@pytest.mark.parametrize("spelling", [
    "claude-haiku-4-5", "claude-haiku-4-5-20251001", "anthropic/claude-haiku-4-5", "openai/anthropic/claude-haiku-4-5",
    "claude-4.5-haiku", "anthropic/claude-4.5-haiku", "claude-haiku-4-5-latest", "global.anthropic.claude-haiku-4-5",
])
def test_every_spelling_of_haiku_4_5_is_one_model(spelling):
    assert ml.parse_model_id(spelling)[:2] == ("haiku", (4, 5))


def test_old_and_new_word_orders_agree():
    assert ml.parse_model_id("claude-3-5-haiku-20241022") == ("haiku", (3, 5), "20241022")
    assert ml.parse_model_id("claude-4-opus-20250514") == ml.parse_model_id("claude-opus-4-20250514")


def test_a_trailing_zero_minor_is_the_major_alias():
    assert ml.parse_model_id("claude-opus-4-0")[:2] == ml.parse_model_id("claude-opus-4")[:2] == ("opus", (4,))


def test_legacy_and_preview_ids_parse():
    assert ml.parse_model_id("claude-2.1") == ("claude", (2, 1), None)
    assert ml.parse_model_id("claude-instant-1.2") == ("instant", (1, 2), None)
    assert ml.parse_model_id("claude-mythos-preview") == ("mythos", ("preview",), None)


@pytest.mark.parametrize("not_a_model", ["claude-code", "claude-cli", "claude-ai", "claude-opus", "claude-code-2",
                                         "claude-docs-v1", "claude"])
def test_tool_and_product_names_are_not_models(not_a_model):
    assert ml.parse_model_id(not_a_model) is None


def test_find_ids_reports_line_numbers_and_skips_non_models():
    text = "x: 1\nmodel: anthropic/claude-3-5-haiku-20241022  # old\nuse claude-code here\n"
    assert ml.find_ids(text) == [(2, "anthropic/claude-3-5-haiku-20241022")]


def test_find_ids_drops_sentence_punctuation():
    assert ml.find_ids("We moved to claude-haiku-4-5. Done.") == [(1, "claude-haiku-4-5")]


def test_find_ids_stays_fast_on_a_long_token_line():
    import time
    t = time.monotonic()
    ml.find_ids("a/" * 50_000 + "x")                        # no `claude-` at all: must not backtrack per position
    assert time.monotonic() - t < 1.0


# ── classification ───────────────────────────────────────────────────────────────────────────────────────────────

def test_a_retired_model_fails(manifest):
    v = ml.classify("claude-3-5-haiku-20241022", manifest, TODAY)
    assert (v.level, v.status) == ("fail", "retired")
    assert "2026-02-19" in v.detail and "claude-haiku-4-5-20251001" in v.detail


def test_an_undated_alias_resolves_to_its_dated_entry(manifest):
    assert ml.classify("claude-haiku-4-5", manifest, TODAY).level == "ok"
    assert ml.classify("claude-3-5-haiku", manifest, TODAY).status == "retired"


def test_deprecated_and_retiring_inside_30_days_fails(manifest):
    v = ml.classify("claude-sonnet-4-5-20250929", manifest, dt.date(2026, 11, 5))   # retires 2026-11-30: 25 days
    assert (v.level, v.status) == ("fail", "retiring")


def test_deprecated_with_more_than_30_days_left_only_warns(manifest):
    v = ml.classify("claude-sonnet-4-5-20250929", manifest, TODAY)                   # 42 days
    assert (v.level, v.status) == ("warn", "deprecated")


def test_deprecated_with_no_retirement_date_warns(manifest):
    assert ml.classify("claude-mythos-preview", manifest, TODAY).level == "warn"


def test_a_deprecated_model_past_its_retirement_date_is_retired_even_if_the_manifest_says_deprecated(manifest):
    assert ml.classify("claude-sonnet-4-5-20250929", manifest, dt.date(2026, 12, 1)).status == "retired"


def test_an_unknown_model_warns_not_passes(manifest):
    v = ml.classify("claude-haiku-9-9", manifest, TODAY)
    assert (v.level, v.status) == ("warn", "unknown")


def test_a_known_family_with_a_different_date_is_unknown(manifest):
    assert ml.classify("claude-haiku-4-5-20990101", manifest, TODAY).status == "unknown"


# ── manifest: missing or malformed is never clean ────────────────────────────────────────────────────────────────

def test_missing_manifest_raises(tmp_path):
    with pytest.raises(ml.ManifestError):
        ml.load_manifest(str(tmp_path / "nope.json"))


@pytest.mark.parametrize("body", ["not json", "{}", '{"models": []}', '{"models": [{"id": "claude-haiku-4-5-20251001"}]}',
                                  '{"models": [{"id": "claude-x", "state": "active"}]}',
                                  '{"models": [{"id": "claude-3-5-haiku-20241022", "state": "retired", "retires": "soon"}]}'])
def test_malformed_manifest_raises(tmp_path, body):
    p = tmp_path / "m.json"
    p.write_text(body)
    with pytest.raises(ml.ManifestError):
        ml.load_manifest(str(p))


# ── the repo scan ────────────────────────────────────────────────────────────────────────────────────────────────

def _tree(tmp_path, files):
    for rel, body in files.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body)
    return str(tmp_path)


def test_scan_names_file_and_line_of_a_retired_id(tmp_path, manifest):
    root = _tree(tmp_path, {"k8s/app/config.yaml": "a: 1\nmodel: claude-3-5-haiku-20241022\n",
                            "k8s/app/ok.yaml": "model: anthropic/claude-haiku-4-5\n"})
    findings, scanned = ml.scan(root, manifest, TODAY)
    assert scanned == 2
    fails = [f for f in findings if f.verdict.level == "fail"]
    assert [(f.path, f.line, f.model_id) for f in fails] == [("k8s/app/config.yaml", 2, "claude-3-5-haiku-20241022")]


def test_scan_skips_docs_history_tests_and_vendored_agent_config(tmp_path, manifest):
    old = "claude-3-opus-20240229\n"
    root = _tree(tmp_path, {"docs/backlog.md": old, "README.md": old, "aidlc/x.yaml": old, ".claude/tools/t.ts": old,
                            "knowledge-repos/k/skill.yaml": old, "svc/tests/test_x.py": old, "scripts/tests/a.bats": old,
                            "svc/test_feeder.py": old, "svc/app.py": "MODEL = 'claude-haiku-4-5'\n"})
    findings, scanned = ml.scan(root, manifest, TODAY)
    assert scanned == 1 and all(f.verdict.level == "ok" for f in findings)


def test_scan_reads_notebook_code_cells_not_their_outputs(tmp_path, manifest):
    nb = {"cells": [{"cell_type": "code", "source": ["m = 'claude-haiku-4-5'\n"],
                     "outputs": [{"text": ["passthroughs: ['anthropic/claude-3-opus-20240229']\n"]}]},
                    {"cell_type": "markdown", "source": ["Old: claude-3-haiku-20240307\n"]}]}
    root = _tree(tmp_path, {"nb/demo.ipynb": json.dumps(nb)})
    findings, scanned = ml.scan(root, manifest, TODAY)
    assert scanned == 1 and [f.model_id for f in findings] == ["claude-haiku-4-5"]


def test_scan_of_an_empty_tree_reports_zero_files(tmp_path, manifest):
    assert ml.scan(str(tmp_path), manifest, TODAY) == ([], 0)


def test_scan_main_exit_codes(tmp_path, capsys):
    bad = _tree(tmp_path / "bad", {"c.yaml": "model: claude-3-5-haiku-20241022\n"})
    good = _tree(tmp_path / "good", {"c.yaml": "model: claude-haiku-4-5\n"})
    env = {"MODEL_GUARD_TODAY": "2026-10-19", "MODEL_MANIFEST": MANIFEST_PATH}
    assert ml.main(["scan", bad], env) == 1
    assert "c.yaml:1" in capsys.readouterr().out
    assert ml.main(["scan", good], env) == 0
    assert ml.main(["scan", str(tmp_path / "empty")], env) == 2                                   # nothing scanned
    assert ml.main(["scan", good], dict(env, MODEL_MANIFEST=str(tmp_path / "none.json"))) == 2   # no manifest


# ── the live check ───────────────────────────────────────────────────────────────────────────────────────────────

MLFLOW = {"model_definitions": [
    {"name": "anthropic-claude-haiku-4-5-md", "provider": "anthropic", "model_name": "claude-haiku-4-5"},
    {"name": "openai-gpt-5-mini-md", "provider": "openai", "model_name": "gpt-5-mini"}]}
BIFROST_KEYS = {"keys": [{"name": "anthropic-env", "enabled": True, "models": ["*"], "blacklisted_models": []}], "total": 1}
BIFROST_VKS = {"virtual_keys": [
    {"name": "realm-llm", "provider_configs": [{"provider": "anthropic", "allowed_models": ["*"]},
                                               {"provider": "groq", "allowed_models": ["*"]}]},
    {"name": "coding-agents", "provider_configs": []}]}
ANTHROPIC = {"data": [{"id": "claude-haiku-4-5-20251001"}, {"id": "claude-sonnet-4-5-20250929"}, {"id": "claude-opus-4-8"}],
             "has_more": False}


def _fetch(overrides=None):
    answers = {"mlflow": MLFLOW, "bifrost_keys": BIFROST_KEYS, "bifrost_vks": BIFROST_VKS, "anthropic": ANTHROPIC}
    answers.update(overrides or {})

    def fetch(source):
        a = answers[source]
        if isinstance(a, Exception):
            raise a
        return a
    return fetch


def test_live_collects_only_anthropic_ids_and_skips_wildcards():
    refs = ml.collect_live_refs(_fetch())
    assert refs == [("mlflow", "anthropic-claude-haiku-4-5-md", "claude-haiku-4-5")]


def test_live_reports_bifrost_ids_when_they_are_pinned():
    keys = {"keys": [{"name": "k", "enabled": True, "models": ["claude-3-5-haiku-20241022"], "blacklisted_models": []}]}
    vks = {"virtual_keys": [{"name": "v", "provider_configs": [{"provider": "anthropic",
                                                               "allowed_models": ["claude-opus-4-8"]}]}]}
    refs = ml.collect_live_refs(_fetch({"bifrost_keys": keys, "bifrost_vks": vks}))
    assert ("bifrost key", "k", "claude-3-5-haiku-20241022") in refs and ("bifrost vk", "v", "claude-opus-4-8") in refs


def test_live_check_passes_on_todays_config(manifest):
    report = ml.live_check(_fetch(), manifest, TODAY)
    assert report.exit_code == 0 and report.offered_count == 3


def test_live_check_fails_on_an_id_the_api_no_longer_offers(manifest):
    report = ml.live_check(_fetch({"anthropic": {"data": [{"id": "claude-opus-4-8"}], "has_more": False}}), manifest, TODAY)
    assert report.exit_code == 1
    assert any("not offered" in line for line in report.lines)


def test_live_check_fails_on_a_retired_id(manifest):
    mlflow = {"model_definitions": [{"name": "old", "provider": "anthropic", "model_name": "claude-3-5-haiku-20241022"}]}
    assert ml.live_check(_fetch({"mlflow": mlflow}), manifest, TODAY).exit_code == 1


@pytest.mark.parametrize("source", ["mlflow", "bifrost_keys", "bifrost_vks", "anthropic"])
def test_live_check_exits_2_when_a_source_cannot_be_read(manifest, source):
    report = ml.live_check(_fetch({source: ml.LiveError(f"{source}: HTTP 401")}), manifest, TODAY)
    assert report.exit_code == 2 and any(source in line for line in report.lines)


def test_live_check_exits_2_on_an_empty_model_list(manifest):
    assert ml.live_check(_fetch({"anthropic": {"data": [], "has_more": False}}), manifest, TODAY).exit_code == 2


def test_live_check_exits_2_on_a_response_of_the_wrong_shape(manifest):
    assert ml.live_check(_fetch({"mlflow": {"unexpected": []}}), manifest, TODAY).exit_code == 2


@pytest.mark.parametrize("missing", ["MLFLOW_URL", "BIFROST_URL", "BIFROST_SETUP_TOKEN", "ANTHROPIC_API_KEY"])
def test_live_main_exits_2_when_a_source_is_not_configured(missing, capsys):
    env = {"MODEL_MANIFEST": MANIFEST_PATH, "MODEL_GUARD_TODAY": "2026-10-19", "MLFLOW_URL": "http://127.0.0.1:9",
           "BIFROST_URL": "http://127.0.0.1:9", "BIFROST_SETUP_TOKEN": "t", "ANTHROPIC_API_KEY": "k"}
    del env[missing]
    fetch = ml._live_fetcher(env)
    source = {"MLFLOW_URL": "mlflow", "BIFROST_URL": "bifrost_keys", "BIFROST_SETUP_TOKEN": "bifrost_vks",
              "ANTHROPIC_API_KEY": "anthropic"}[missing]
    with pytest.raises(ml.LiveError, match=missing):
        fetch(source)


def test_anthropic_listing_pages_until_has_more_is_false():
    pages = [{"data": [{"id": "claude-opus-4-8"}], "has_more": True, "last_id": "claude-opus-4-8"},
             {"data": [{"id": "claude-haiku-5-5"}], "has_more": False}]
    seen = []

    def get_json(url, headers):
        seen.append(url)
        return pages[len(seen) - 1]
    assert ml.list_anthropic_models(get_json, "https://api.anthropic.com", "k") == ["claude-opus-4-8", "claude-haiku-5-5"]
    assert "after_id=claude-opus-4-8" in seen[1]
