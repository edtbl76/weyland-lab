"""Tests for onnx_export.py (B216) — export each model at a pinned commit, then prove the export reproduces recorded output.

Only the decisions are tested here (spec validation, fingerprinting, comparison, exit codes). The export itself needs
torch + optimum and runs inside the Docker export stages, where a mismatch fails the image build; the probe needs
onnxruntime + tokenizers and is run against the deployed images (B216's record step).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import onnx_export as ox  # noqa: E402

SHA = "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a"


def _model(**over):
    m = {"repo": "BAAI/bge-base-en-v1.5", "revision": SHA, "task": "feature-extraction", "out": "/export/bge_onnx",
         "expected": {"cls_head": [0.1, -0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], "cls_norm": 12.5}}
    m.update(over)
    return m


def _spec(models=None, **over):
    s = {"probe": "Weyland pins every model it exports.", "tolerance": 1e-5, "models": models or [_model()]}
    s.update(over)
    return s


def _write(tmp_path, spec):
    p = tmp_path / "onnx_models.json"
    p.write_text(json.dumps(spec))
    return str(p)


# ── the spec ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_valid_spec_loads(tmp_path):
    spec = ox.load_spec(_write(tmp_path, _spec()))
    assert spec["models"][0]["repo"] == "BAAI/bge-base-en-v1.5"


@pytest.mark.parametrize("bad, reason", [
    ({"revision": "main"}, "40-hex commit"),
    ({"revision": "a5beb1e3"}, "40-hex commit"),
    ({"task": "translation"}, "task"),
    ({"out": "relative/dir"}, "absolute"),
    ({"expected": None}, "expected"),
    ({"expected": {"cls_head": [0.1]}}, "cls_norm"),
])
def test_a_spec_that_does_not_pin_or_check_is_refused(tmp_path, bad, reason):
    with pytest.raises(ox.SpecError, match=reason):
        ox.load_spec(_write(tmp_path, _spec([_model(**bad)])))


def test_a_classifier_needs_logits(tmp_path):
    clf = _model(repo="cross-encoder/nli-deberta-v3-small", task="text-classification", out="/export/nli_onnx",
                 expected={"logits": [1.0, -2.0, 0.5]})
    assert ox.load_spec(_write(tmp_path, _spec([clf])))["models"][0]["task"] == "text-classification"
    with pytest.raises(ox.SpecError, match="logits"):
        ox.load_spec(_write(tmp_path, _spec([dict(clf, expected={"cls_head": [1.0], "cls_norm": 1.0})])))


@pytest.mark.parametrize("body", ["not json", "{}", '{"probe": "x", "models": []}', '{"models": [{"repo": "x"}]}'])
def test_a_malformed_or_empty_spec_is_refused(tmp_path, body):
    p = tmp_path / "s.json"
    p.write_text(body)
    with pytest.raises(ox.SpecError):
        ox.load_spec(str(p))


def test_a_missing_spec_is_refused(tmp_path):
    with pytest.raises(ox.SpecError, match="cannot read"):
        ox.load_spec(str(tmp_path / "nope.json"))


def test_a_spec_with_no_probe_text_is_refused(tmp_path):
    with pytest.raises(ox.SpecError, match="probe"):
        ox.load_spec(_write(tmp_path, _spec(probe="")))


# ── fingerprints ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_feature_fingerprint_is_the_cls_head_and_its_norm():
    hidden = [[[3.0, 4.0] + [0.0] * 10, [9.0] * 12]]           # batch 1, two tokens; CLS = token 0
    fp = ox.fingerprint("feature-extraction", hidden)
    assert fp["cls_head"] == [3.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert fp["cls_norm"] == pytest.approx(5.0)


def test_classifier_fingerprint_is_the_logits():
    assert ox.fingerprint("text-classification", [[1.5, -0.5, 0.25]]) == {"logits": [1.5, -0.5, 0.25]}


# ── comparison ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_identical_output_matches():
    exp = {"cls_head": [0.1, 0.2], "cls_norm": 3.0}
    assert ox.compare(exp, dict(exp), 1e-5) == []


def test_a_difference_inside_tolerance_matches():
    assert ox.compare({"logits": [1.0, 2.0]}, {"logits": [1.000001, 2.0]}, 1e-5) == []


def test_a_difference_outside_tolerance_is_named():
    diffs = ox.compare({"cls_head": [0.1, 0.2], "cls_norm": 3.0}, {"cls_head": [0.1, 0.25], "cls_norm": 3.0}, 1e-5)
    assert len(diffs) == 1 and "cls_head[1]" in diffs[0] and "0.2" in diffs[0] and "0.25" in diffs[0]


def test_a_length_change_is_a_difference():
    assert ox.compare({"logits": [1.0, 2.0]}, {"logits": [1.0, 2.0, 3.0]}, 1e-5)


def test_a_missing_field_is_a_difference():
    assert ox.compare({"logits": [1.0]}, {}, 1e-5)


# ── the build check: exit codes and the model named on failure ───────────────────────────────────────────────────

def _run(tmp_path, spec, actual_by_repo, capsys, argv_extra=()):
    exported = []

    def export(model):
        exported.append((model["repo"], model["revision"]))

    def probe(model, text):
        return actual_by_repo[model["repo"]]

    code = ox.main(["build", _write(tmp_path, spec), *argv_extra], export=export, probe=probe)
    return code, exported, capsys.readouterr().out


def test_build_exports_every_model_at_its_pinned_revision_and_passes(tmp_path, capsys):
    m = _model()
    code, exported, out = _run(tmp_path, _spec([m]), {m["repo"]: dict(m["expected"])}, capsys)
    assert code == 0 and exported == [("BAAI/bge-base-en-v1.5", SHA)]
    assert "OK BAAI/bge-base-en-v1.5@a5beb1e3" in out


def test_build_fails_naming_the_model_whose_output_changed(tmp_path, capsys):
    m = _model()
    changed = dict(m["expected"], cls_norm=13.0)
    code, _, out = _run(tmp_path, _spec([m]), {m["repo"]: changed}, capsys)
    assert code == 1
    assert "MISMATCH BAAI/bge-base-en-v1.5@a5beb1e3" in out and "cls_norm" in out


def test_build_exits_2_on_a_bad_spec(tmp_path, capsys):
    code, exported, out = _run(tmp_path, _spec([_model(revision="main")]), {}, capsys)
    assert code == 2 and exported == [] and "40-hex commit" in out


def test_the_record_build_arg_turns_on_record_mode(tmp_path, capsys, monkeypatch):
    m = _model()
    monkeypatch.setenv("ONNX_EXPORT_RECORD", "1")
    code, _, out = _run(tmp_path, _spec([m]), {m["repo"]: {"cls_head": [9.0] * 8, "cls_norm": 1.0}}, capsys)
    assert code == 0 and '"cls_norm": 1.0' in out


def test_an_unset_or_empty_record_arg_still_checks(tmp_path, capsys, monkeypatch):
    m = _model()
    monkeypatch.setenv("ONNX_EXPORT_RECORD", "")
    code, _, _ = _run(tmp_path, _spec([m]), {m["repo"]: {"cls_head": [9.0] * 8, "cls_norm": 1.0}}, capsys)
    assert code == 1


def test_the_default_tolerance_is_the_acceptance_bound(tmp_path):
    spec = _spec()
    del spec["tolerance"]
    assert ox.load_spec(_write(tmp_path, spec))["tolerance"] == 1e-6


def test_record_mode_prints_the_actual_fingerprint_and_never_fails(tmp_path, capsys):
    m = _model()
    code, _, out = _run(tmp_path, _spec([m]), {m["repo"]: {"cls_head": [9.0] * 8, "cls_norm": 1.0}}, capsys,
                        argv_extra=("--record",))
    assert code == 0
    assert json.loads(out.strip().splitlines()[-1])["BAAI/bge-base-en-v1.5"]["cls_norm"] == 1.0
