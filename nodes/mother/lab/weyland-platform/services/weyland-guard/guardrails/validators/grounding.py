import math

from ..verdict import Verdict, Decision, Hook

_DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-small"


def _entailment_score(pred) -> float:
    """Reduce one cross-encoder prediction to an entailment probability in [0, 1].

    NLI cross-encoders (e.g. nli-deberta-v3-small) emit THREE logits per pair, ordered
    [contradiction, entailment, neutral] — we softmax and take the entailment term (index 1).
    Plain similarity cross-encoders emit a single scalar; we pass that through unchanged. This
    makes the validator robust to either model family (and to numpy scalars/rows alike)."""
    try:
        seq = [float(x) for x in pred]      # a row of logits, or raises if pred is scalar
    except TypeError:
        return float(pred)                  # scalar similarity score
    if len(seq) == 1:
        return seq[0]
    m = max(seq)
    exps = [math.exp(x - m) for x in seq]   # numerically-stable softmax
    return exps[1] / sum(exps)              # index 1 = entailment


class GroundingValidator:
    """Hallucination check: is the answer entailed by the retrieved source chunks?

    Scores each (source_chunk, answer) pair with an NLI cross-encoder and takes the max
    entailment probability. Below `threshold` => FLAG (unsupported / likely hallucinated).
    The cross-encoder is injectable so tests run without downloading a model.
    """

    name = "grounding.nli"
    hooks = (Hook.OUTPUT,)

    def __init__(self, cross_encoder=None, threshold: float = 0.5, model_name: str = _DEFAULT_MODEL):
        if cross_encoder is None:
            from sentence_transformers import CrossEncoder
            cross_encoder = CrossEncoder(model_name)
        self._ce = cross_encoder
        self._threshold = threshold

    def check(self, payload: dict, hook: Hook) -> Verdict:
        answer = payload.get("answer", "") or ""
        sources = payload.get("sources", []) or []
        if not answer or not sources:
            return Verdict(self.name, Decision.PASS, None, "no answer/sources to check", 0)
        pairs = [(s.get("content", "") or "", answer) for s in sources]
        score = max(_entailment_score(p) for p in self._ce.predict(pairs))
        decision = Decision.PASS if score >= self._threshold else Decision.FLAG
        return Verdict(self.name, decision, score, f"max_entailment={score:.3f}", 0)
