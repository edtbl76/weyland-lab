import math
import re

from ..verdict import Verdict, Decision, Hook

_DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-small"

# Sentence splitter: break after . ! ? followed by whitespace. Deliberately simple (no nltk) —
# it only has to isolate claims, not be linguistically perfect.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Fragments shorter than this are framing ("In summary:", "Here's what I found:") — no claim to
# ground, and they would only drag the grounding score down.
_MIN_CLAIM_CHARS = 20


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


def _split_claims(answer: str) -> list[str]:
    """Split an answer into claim-bearing sentences, dropping short framing fragments. Falls back
    to the whole answer if nothing survives (e.g. a single terse sentence)."""
    parts = [s.strip() for s in _SENT_SPLIT.split(answer.strip()) if s.strip()]
    claims = [s for s in parts if len(s) >= _MIN_CLAIM_CHARS]
    return claims or [answer.strip()]


class GroundingValidator:
    """Hallucination check: is every claim in the answer entailed by some retrieved chunk?

    Scores each (source_chunk, answer_SENTENCE) pair with an NLI cross-encoder, takes the max
    entailment per sentence (its best-supporting chunk), then aggregates across sentences (mean).
    Below `threshold` => FLAG (unsupported / likely hallucinated). The cross-encoder is injectable
    so tests run without downloading a model.

    B35 calibration change: the earlier design scored (chunk, WHOLE answer) and took the max — but a
    multi-sentence answer is never entailed by any single short chunk, so it over-flagged grounded
    answers (58% of shadow verdicts flagged at threshold 0.5, against a measured RAG faithfulness of
    ~0.81). Per-claim scoring measures grounding ("is each claim supported by some chunk") rather
    than "is the whole answer contained in one chunk", and — unlike a single concatenated premise —
    keeps every pair small, avoiding the cross-encoder's ~512-token truncation that would silently
    drop the chunks supporting an answer's tail.
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
        contents = [c for c in ((s.get("content", "") or "").strip() for s in sources) if c]
        if not contents:
            return Verdict(self.name, Decision.PASS, None, "no non-empty sources to check", 0)

        claims = _split_claims(answer)
        # One flat batch of (chunk, claim) pairs, ordered claim-major; reshape to per-claim max.
        pairs = [(chunk, claim) for claim in claims for chunk in contents]
        flat = [_entailment_score(p) for p in self._ce.predict(pairs)]
        n = len(contents)
        per_claim = [max(flat[i * n:(i + 1) * n]) for i in range(len(claims))]

        score = sum(per_claim) / len(per_claim)   # mean grounding across claims (the verdict score)
        weakest = min(per_claim)                  # least-supported claim — kept for threshold calibration
        decision = Decision.PASS if score >= self._threshold else Decision.FLAG
        return Verdict(self.name, decision, score,
                       f"grounded_mean={score:.3f} weakest={weakest:.3f} claims={len(claims)}", 0)
