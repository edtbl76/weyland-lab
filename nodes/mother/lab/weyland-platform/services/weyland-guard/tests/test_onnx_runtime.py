"""U13 raw-ONNX-Runtime adapters (OnnxCrossEncoder / OnnxTextClassifier).

The real classes load `model.onnx` + `tokenizer.json` and run onnxruntime — none of which exist in the test
env — so we stub `onnxruntime` + `tokenizers` into sys.modules BEFORE importing the module (the same technique
test_safety_validators uses for transformers/httpx/presidio). What these cover is the DECISION logic on top of
the runtime: batching + concat + shape for the cross-encoder, and softmax + id2label label mapping for the
classifier. The byte-equivalence of the models themselves is proven in-image at build (U13 spike), not here.
"""
import json
import sys
import types

import numpy as np
import pytest


class _Enc:
    def __init__(self, ids):
        self.ids = ids
        self.attention_mask = [1] * len(ids)
        self.type_ids = [0] * len(ids)


def _install_fakes(logits_row, input_names=("input_ids", "attention_mask")):
    """Stub onnxruntime + tokenizers so the adapters load no real model. The fake session returns
    `logits_row` for every item in the batch (shape (batch, len(logits_row)))."""
    class _Sess:
        def __init__(self, *a, **k):
            pass

        def get_inputs(self):
            return [types.SimpleNamespace(name=n) for n in input_names]

        def run(self, _out, feed):
            batch = len(next(iter(feed.values())))
            return [np.array([logits_row] * batch, dtype=float)]

    ort = types.ModuleType("onnxruntime")
    ort.InferenceSession = _Sess
    sys.modules["onnxruntime"] = ort

    class _Tok:
        def enable_truncation(self, *a, **k):
            pass

        def enable_padding(self, *a, **k):
            pass

        def encode(self, text):
            return _Enc([1, 2, 3])

        def encode_batch(self, items):
            return [_Enc([1, 2, 3]) for _ in items]

        @classmethod
        def from_file(cls, path):
            return cls()

    tok = types.ModuleType("tokenizers")
    tok.Tokenizer = _Tok
    sys.modules["tokenizers"] = tok


def _onnx_runtime():
    import guardrails.validators.onnx_runtime as m
    return m


# ---------------------------------------------------------------- OnnxCrossEncoder (grounding.nli)

def test_cross_encoder_predict_batches_and_concats():
    _install_fakes([2.0, 5.0, 1.0])   # 3-logit NLI row
    ce = _onnx_runtime().OnnxCrossEncoder("/nonexistent")
    # batch_size=1 with 3 pairs forces THREE forward passes that must concat to one (3, 3) array.
    out = ce.predict([("a", "b"), ("c", "d"), ("e", "f")], batch_size=1)
    assert out.shape == (3, 3)
    assert np.allclose(out[0], [2.0, 5.0, 1.0])   # entailment (index 1) is the max, as grounding expects


def test_cross_encoder_predict_empty_pairs():
    _install_fakes([0.0, 0.0, 0.0])
    ce = _onnx_runtime().OnnxCrossEncoder("/nonexistent")
    out = ce.predict([])
    assert out.shape == (0, 0)   # empty in → empty out, no forward pass


# ---------------------------------------------------------------- OnnxTextClassifier (prompt_guard)

def test_text_classifier_softmaxes_and_labels(tmp_path):
    _install_fakes([4.0, 0.0])   # 2-class: LABEL_0 dominant
    (tmp_path / "config.json").write_text(json.dumps({"id2label": {"0": "LABEL_0", "1": "LABEL_1"}}))
    clf = _onnx_runtime().OnnxTextClassifier(str(tmp_path))
    scores = clf("some prompt text")
    assert [s["label"] for s in scores] == ["LABEL_0", "LABEL_1"]
    assert sum(s["score"] for s in scores) == pytest.approx(1.0)   # softmax normalized
    assert scores[0]["score"] > scores[1]["score"]                 # LABEL_0 wins


def test_text_classifier_falls_back_to_label_indices_without_id2label(tmp_path):
    _install_fakes([1.0, 1.0])
    (tmp_path / "config.json").write_text(json.dumps({}))   # no id2label → LABEL_0/LABEL_1 fallback
    clf = _onnx_runtime().OnnxTextClassifier(str(tmp_path))
    scores = clf("x")
    assert [s["label"] for s in scores] == ["LABEL_0", "LABEL_1"]
    assert scores[0]["score"] == pytest.approx(0.5)
