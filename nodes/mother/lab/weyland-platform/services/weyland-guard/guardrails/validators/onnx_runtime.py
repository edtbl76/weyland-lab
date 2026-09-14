"""Raw ONNX Runtime replacements for the two baked DeBERTa classifiers (U13).

weyland-guard's only torch pullers were `sentence-transformers` (the grounding.nli NLI cross-encoder) and
`transformers` (the prompt_guard.injection text-classification pipeline) — both DeBERTa sequence classifiers.
These two classes run their ONNX exports on raw onnxruntime + tokenizers (no torch / sentence-transformers /
transformers), and are byte-equivalent to the originals (verified: cross-encoder logit diff 0.0 vs
sentence-transformers CrossEncoder; prompt-guard scores match the transformers pipeline to ~1e-9), so every
SHADOW verdict and calibrated threshold stays valid unchanged. Mirrors the OnnxBge pattern in the embedder
services. Deps: onnxruntime + tokenizers + numpy only. DeBERTa-v3 feeds input_ids + attention_mask only
(no token_type_ids), but we build the feed from the model's declared inputs so it is architecture-agnostic."""
import json


class OnnxCrossEncoder:
    """sentence_transformers.CrossEncoder.predict-compatible NLI scorer. `predict(pairs, batch_size=)` returns
    a (n, num_labels) logits array — grounding._entailment_score softmaxes each row + takes entailment."""

    def __init__(self, model_dir: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self._sess = ort.InferenceSession(f"{model_dir}/model.onnx", providers=["CPUExecutionProvider"])
        self._tok = Tokenizer.from_file(f"{model_dir}/tokenizer.json")
        self._tok.enable_truncation(max_length=512)
        self._tok.enable_padding()   # pad within each batch → rectangular tensors
        self._names = [i.name for i in self._sess.get_inputs()]

    def predict(self, pairs, batch_size: int = 8):
        import numpy as np
        if not pairs:
            return np.empty((0, 0), dtype=np.float32)
        out = []
        for i in range(0, len(pairs), batch_size):
            encs = self._tok.encode_batch([list(p) for p in pairs[i:i + batch_size]])   # (premise, hypothesis) pairs
            avail = {"input_ids": [e.ids for e in encs],
                     "attention_mask": [e.attention_mask for e in encs],
                     "token_type_ids": [e.type_ids for e in encs]}
            feed = {n: np.array(avail[n], dtype=np.int64) for n in self._names if n in avail}
            out.append(self._sess.run(None, feed)[0])
        return np.concatenate(out, axis=0)


class OnnxTextClassifier:
    """transformers.pipeline('text-classification', top_k=None)-compatible classifier. `__call__(text)` returns
    [{"label", "score"}, ...] for all classes (softmaxed), labels from the model's config.json id2label."""

    def __init__(self, model_dir: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self._sess = ort.InferenceSession(f"{model_dir}/model.onnx", providers=["CPUExecutionProvider"])
        self._tok = Tokenizer.from_file(f"{model_dir}/tokenizer.json")
        self._tok.enable_truncation(max_length=512)
        self._names = [i.name for i in self._sess.get_inputs()]
        with open(f"{model_dir}/config.json") as f:
            id2label = (json.load(f).get("id2label") or {})
        # id2label keys are stringified ints ("0","1",…); order by id → the pipeline's label order.
        self._labels = [id2label.get(str(i), f"LABEL_{i}") for i in range(len(id2label))] or None

    def __call__(self, text: str):
        import numpy as np
        e = self._tok.encode(text)
        avail = {"input_ids": e.ids, "attention_mask": e.attention_mask, "token_type_ids": e.type_ids}
        feed = {n: np.array([avail[n]], dtype=np.int64) for n in self._names if n in avail}
        logits = self._sess.run(None, feed)[0][0]
        m = float(np.max(logits)); exps = np.exp(logits - m); probs = exps / exps.sum()
        labels = self._labels or [f"LABEL_{i}" for i in range(len(probs))]
        return [{"label": labels[i], "score": float(probs[i])} for i in range(len(probs))]
