import math
import os
import re
import threading

from ..verdict import Verdict, Decision, Hook

_DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-small"

# B35 calibrated threshold. grounding.nli measures chunk-ATTRIBUTABILITY (is the answer traceable to
# the retrieved chunks), NOT truth/faithfulness — good conceptual answers legitimately synthesize
# beyond sparse chunks and score mid-low. Labeled shadow data (golden set) put the genuinely-
# unattributable tail (retrieval misses + heavy elaboration) below ~0.15, while the guessed 0.5
# flagged ~50%, including attributable answers. Env-overridable to retune as shadow data accrues.
# Stays SHADOW (advisory) — real faithfulness gating is the LLM-judge lane (B84), not NLI.
_DEFAULT_THRESHOLD = float(os.getenv("GROUNDING_THRESHOLD", "0.15"))

# Split on sentence punctuation OR newlines — RAG answers are often markdown lists whose items are
# newline-separated, not .!?-separated; splitting on .!? alone shreds "1. **Awareness** – ..." into
# junk fragments that entail poorly.
_CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
# Formatting noise that degrades NLI entailment against prose chunks. The STORED answer keeps its
# markdown; only the text we score is normalized: citation markers, emphasis, leading list markers.
_CITATION = re.compile(r"【[^】]*】|\[\d+\]")
_MD_EMPHASIS = re.compile(r"[*_#`]+")
_LIST_MARKER = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s+")
# Fragments shorter than this are framing ("In summary:", "Here's what I found:") — no claim to
# ground, and they would only drag the grounding score down.
_MIN_CLAIM_CHARS = 20

# Bound the per-check NLI work so grounding can't OOM the pod (it did at 2Gi: sentence-level scoring
# runs up to claims×chunks pairs, and the pipeline runs shadow validators in a threadpool, so spaced
# requests stacked concurrent forward passes on top of ~1.5GB of resident models). Three guards:
#   _MAX_CLAIMS   — cap claims scored, so a long answer can't blow up the pair count (runtime bound).
#   _PREDICT_BATCH— small cross-encoder batch, so peak activation memory stays flat (memory bound).
#   _PREDICT_LOCK — serialize inference across shadow threads, so at most one forward pass runs at a
#                   time. Grounding is off the response path, so serializing costs nothing visible.
_MAX_CLAIMS = 12
_PREDICT_BATCH = 8
_PREDICT_LOCK = threading.Lock()


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
    """Split an answer into claim-bearing units and normalize each for NLI. RAG answers are commonly
    markdown (numbered/bulleted lists, **bold**, 【1】 citations); splitting on .!? alone mangles those
    into junk fragments that entail poorly against prose chunks — so we also split on newlines and
    strip the formatting noise. Short framing fragments are dropped; falls back to the whole answer
    if nothing survives (e.g. a single terse sentence)."""
    claims = []
    for part in _CLAIM_SPLIT.split(answer.strip()):
        s = _LIST_MARKER.sub("", part)
        s = _CITATION.sub("", s)
        s = _MD_EMPHASIS.sub("", s)
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) >= _MIN_CLAIM_CHARS:
            claims.append(s)
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

    def __init__(self, cross_encoder=None, threshold: float | None = None, model_name: str = _DEFAULT_MODEL):
        if cross_encoder is None:
            from sentence_transformers import CrossEncoder
            cross_encoder = CrossEncoder(model_name)
        self._ce = cross_encoder
        self._threshold = _DEFAULT_THRESHOLD if threshold is None else threshold

    def check(self, payload: dict, hook: Hook) -> Verdict:
        answer = payload.get("answer", "") or ""
        sources = payload.get("sources", []) or []
        if not answer or not sources:
            return Verdict(self.name, Decision.PASS, None, "no answer/sources to check", 0)
        contents = [c for c in ((s.get("content", "") or "").strip() for s in sources) if c]
        if not contents:
            return Verdict(self.name, Decision.PASS, None, "no non-empty sources to check", 0)

        claims = _split_claims(answer)[:_MAX_CLAIMS]
        # One flat batch of (chunk, claim) pairs, ordered claim-major; reshape to per-claim max.
        # Serialized + small-batched so peak memory stays flat regardless of answer length or load.
        pairs = [(chunk, claim) for claim in claims for chunk in contents]
        with _PREDICT_LOCK:
            flat = [_entailment_score(p) for p in self._ce.predict(pairs, batch_size=_PREDICT_BATCH)]
        n = len(contents)
        per_claim = [max(flat[i * n:(i + 1) * n]) for i in range(len(claims))]

        score = sum(per_claim) / len(per_claim)   # mean grounding across claims (the verdict score)
        weakest = min(per_claim)                  # least-supported claim — kept for threshold calibration
        decision = Decision.PASS if score >= self._threshold else Decision.FLAG
        return Verdict(self.name, decision, score,
                       f"grounded_mean={score:.3f} weakest={weakest:.3f} claims={len(claims)}", 0)
