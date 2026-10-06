#!/usr/bin/env python3
"""Issue-readiness scorer — is a Linear issue ready to hand to a coding agent? (B190, replaces SpecBot)

SpecBot, a third-party cloud judge (25 analyses/month, opaque rubric and model), scored EMA-240 51/100 on 2026-09-25 and
exposed a real gap: issues written as Why + Scope with no definition of done. This is the lab's own version, built so CI
can trust it:

  1. DETERMINISTIC CHECKS FIRST. A section a rule can judge (no Acceptance criteria, only the template placeholder, a bug
     with no repro, no priority set) is scored by the rule and never sent to the model — cheap, explainable, and a 7B
     judge cannot talk its way past a missing definition of done.
  2. THE MODEL JUDGES THE REST through LiteLLM's `wl-judge-oss` alias (free local gpt-oss:20b, 16K-window build),
     temperature 0, JSON only. The reply is validated: every requested dimension, integers 0-100. One retry, then exit
     2 — a malformed or partial judgement is never turned into a score. Every score of 50+ must quote the issue; a
     quote the issue does not contain caps that dimension at 40 (the code checks, not the model). qwen2.5:7b was
     tried first and rejected on calibration (2026-10-06): it rated every present section 90-100 and wrote its
     reasons where the quotes belonged.
  3. THE TOTAL IS THE ROUNDED MEAN of the applicable dimensions — SpecBot's own formula (EMA-240's 51/70/75 are exact
     means of its 8), minus `reproduction` on anything that is not a bug, where it means nothing.
  4. ONE COMMENT PER ISSUE, updated in place on a re-score (found by MARKER + our own user), naming the model that
     actually answered and the rubric version, so a score can be traced when either changes.

Exit codes:  0 READY (>= 80, no blockers) or skipped  ·  1 NOT READY  ·  2 scorer unavailable / invalid / usage.

  issue_readiness.py EMA-249                      score one issue and upsert its comment
  issue_readiness.py EMA-249 --no-comment --json  score only, machine-readable
  issue_readiness.py --sweep                      every open High issue in project Weyland Lab (the lean-CI step)
  issue_readiness.py --issue-file issue.json      score a saved issue (offline; calibration and tests)

Env: LITELLM_API_KEY (required) · LITELLM_API_BASE (default http://192.168.1.243:30400) · ISSUE_READINESS_MODEL
(default wl-judge-oss) · LINEAR_API_KEY (write scope to comment). Runbook: docs/runbooks/issue-readiness.md.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

RUBRIC_VERSION = "2"                    # 2: priority_scope demands concrete exclusions (judge eval, 2026-10-06)
THRESHOLD = 80
MAX_DESCRIPTION_CHARS = 20000          # ~5K tokens: with the rubric, well inside one 16K Ollama slot of the 32K build
MARKER = "**Issue readiness (weyland scorer)**"
SWEEP_PROJECT = "Weyland Lab"
DEFAULT_VOTES = 3                      # judgements per score; the median per dimension (see vote())
DEFAULT_MODEL = "wl-judge-oss"         # gpt-oss:20b, 16K build — the 7B (wl-judge) could not judge (see module doc)
LINEAR_URL = "https://api.linear.app/graphql"

DIMENSIONS = (
    ("objective", "Objective / problem"),
    ("expected_behavior", "Expected behavior"),
    ("acceptance_criteria", "Acceptance criteria"),
    ("edge_cases", "Edge cases"),
    ("technical_context", "Technical context"),
    ("dependencies", "Dependencies"),
    ("reproduction", "Reproduction steps"),
    ("priority_scope", "Priority and scope clarity"),
)
LABEL = dict(DIMENSIONS)

RUBRIC = {
    "objective": "Is the problem stated, with why it matters? 90+: a concrete problem and its consequence. "
                 "<40: no problem stated, only a solution.",
    "expected_behavior": "Is the end state described — what is true when this is done? 90+: the outcome is "
                         "specific. <40: a vague goal.",
    "acceptance_criteria": "Are there testable pass/fail checks someone or an agent can run? 90+: each criterion "
                           "is a runnable check. <40: none, or only aspirations.",
    "edge_cases": "Are failure modes, absent inputs and boundaries named, with the expected behavior? 90+: the "
                  "realistic ones, each with what should happen.",
    "technical_context": "Are the affected systems, files, services and APIs named (host, path, role)? 90+: an "
                         "agent knows where to look without searching.",
    "dependencies": "Are prerequisites, blockers and related items named, or is it clear there are none? 90+: "
                    "explicit. <40: obviously depends on things it does not name.",
    "reproduction": "Bug only: can the failure be reproduced from the steps given? 90+: exact steps and evidence.",
    "priority_scope": "Is it clear where the work stops and why it matters now? Judge the Out of scope list first: "
                      "90+: it names concrete things this issue will NOT do. An Out of scope list that names nothing "
                      "concrete ('nothing in particular', 'TBD', a generic phrase) scores below 40 whatever else is "
                      "written. Never penalize a missing estimate.",
}

PREAMBLE = "(opening paragraph)"        # text before the first heading — how EMA-240 / EMA-243 state their problem

SECTION_ALIASES = {
    "objective": ("why", "purpose", "observed", "questions to answer", "problem", PREAMBLE),
    "expected_behavior": ("expected", "goal", "outcome", "deliverable", "definition of done", "end state"),
    "dependencies": ("dependencies", "depends on", "blocked by", "prerequisites", "relates", "related"),
    "acceptance_criteria": ("acceptance criteria", "exit criteria"),
    "edge_cases": ("edge cases",),
    "technical_context": ("technical context",),
    "reproduction": ("repro", "steps to reproduce"),
    "out_of_scope": ("out of scope", "in scope / out of scope"),
}

# Guidance lines the Linear templates pre-fill — a section holding only these is still empty.
TEMPLATE_GUIDANCE = (
    "testable, pass/fail", "what breaks, what's absent", "affected systems, files, services",
    "the regression test fails on the bug", "| where | what | role |", "| -- | -- | -- |", "(host / repo)",
)
PLACEHOLDER_LINE = re.compile(r"^\s*([-*]\s*(\[[ x]\])?\s*)?(\([^)]*\))?\s*$")

# (max score, reason, fix) when a section a rule can see is missing. The model may score lower, never higher.
CAPS = {
    "objective": (50, "No Why / problem statement.", "Add a Why section: the problem and why it matters."),
    "expected_behavior": (50, "No Expected behavior / outcome section — what is true when done is unstated.",
                          "Add an Expected behavior section: what is true when this is done."),
    "technical_context": (50, "No Technical context section.",
                          "Add a Technical context section: affected systems, files and services (host, path, role)."),
    "out_of_scope": (60, "No Out of scope section — where the work stops is unstated.", "Add an Out of scope list."),
    "priority": (30, "No priority set on the issue.", "Set the issue's priority field."),
}

BLOCKER_TEXT = {
    "acceptance_criteria": "Add explicit acceptance criteria that define done.",
    "objective": "State the problem this solves and why it matters.",
    "reproduction": "Add reproduction steps and the evidence of the failure.",
}


class ScorerUnavailable(Exception):
    """The judge could not be reached (gateway down, auth refused, timeout)."""


class ScorerInvalid(Exception):
    """The judge answered, but not with a usable judgement (after one retry)."""


class LinearError(Exception):
    """Linear could not be read or written."""


@dataclass
class Issue:
    identifier: str
    uuid: str
    title: str
    description: str
    priority: int                       # Linear native field: 0 none, 1 urgent, 2 high, 3 medium, 4 low
    labels: list = field(default_factory=list)
    project: str = None
    relations: int = 0                  # Linear blocks / blocked-by / related links, both directions


EVIDENCE_FLOOR = 50                     # a score at or above this must cite the issue
UNSUPPORTED_CAP = 40
JUDGE_MAX = 90                          # qwen2.5:7b scored nearly every present section 95-100 (2026-10-06)
QUOTE_MATCH = 0.6                       # share of the quote's 3-word runs that must appear in the issue


@dataclass
class Score:
    score: int
    reason: str
    fix: str = ""
    source: str = "llm"                 # "rule" when a deterministic check decided it
    evidence: str = ""                  # the judge's verbatim quote from the issue supporting the score


@dataclass
class Plan:
    fixed: dict                          # dim -> Score, decided by a rule (never sent to the model)
    caps: dict                           # dim -> (max score, reason, fix) applied to the model's score
    na: set                              # dims that do not apply to this kind of issue
    judged: list                         # dims the model is asked for


@dataclass
class Result:
    identifier: str
    kind: str
    scores: dict = field(default_factory=dict)
    na: set = field(default_factory=set)
    total: int = None
    status: str = None
    blockers: list = field(default_factory=list)
    fixes: list = field(default_factory=list)
    model: str = None
    confidence: int = None
    truncated: bool = False
    skipped: str = None
    digest: str = None


# ── reading the issue ───────────────────────────────────────────────────────


HEADING = re.compile(r"^#{1,4}\s+(?P<h>.*?)\s*#*\s*$")
# A bold run that OPENS a line and is short is a pseudo-heading ("**Why.** It broke." / "**Acceptance criteria**") —
# EMA-240 and the backlog-style issues are written that way. Bold mid-sentence is emphasis, not a section.
BOLD_HEADING = re.compile(r"^\*\*(?P<h>[^*\n]{2,48}?)[.:]?\*\*[.:]?\s*(?P<rest>.*)$")


def parse_sections(markdown):
    """{lowercased heading text: body} for `#` headings and line-opening bold pseudo-headings."""
    sections, current = {PREAMBLE: ""}, PREAMBLE
    for line in (markdown or "").splitlines():
        m = HEADING.match(line) or BOLD_HEADING.match(line)
        if m:
            current = m.group("h").strip().rstrip(".:").lower()
            sections[current] = (m.groupdict().get("rest") or "") + "\n"
        else:
            sections[current] += line + "\n"
    if not sections[PREAMBLE].strip():
        del sections[PREAMBLE]
    return sections


def _normalize(text):
    return " ".join(re.sub(r"[*_`>#|]", " ", text or "").lower().split())


def _trigrams(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}


def quoted(evidence, description):
    """True when the judge's quote really comes from the issue. A small model keeps list markers, joins two bullets
    or trims a clause (observed live on EMA-254), so the test is that most of the quote's 3-word runs occur in the
    issue — an invented sentence shares almost none."""
    needle = _trigrams(evidence)
    return len(needle) >= 2 and len(needle & _trigrams(description)) / len(needle) >= QUOTE_MATCH


DEPENDENCY_TEXT = re.compile(r"\b(depends on|blocked by|blocks|prerequisite|requires|relates to|follow-on|after)"
                             r"\s+(B\d+|EMA-\d+|U\d+)|\bdependencies\b[^.\n]{0,20}\bnone\b", re.I)


def states_dependencies(issue, sections):
    return bool(issue.relations) or has_section(sections, "dependencies") or bool(
        DEPENDENCY_TEXT.search(issue.description or ""))


def _meaningful(body):
    """True when a section holds real content, not just the template's guidance and placeholders."""
    kept = [ln for ln in body.splitlines()
            if not PLACEHOLDER_LINE.match(ln) and not any(g in ln.lower() for g in TEMPLATE_GUIDANCE)]
    return len(re.findall(r"[A-Za-z0-9]", " ".join(kept))) >= 6     # placeholders are already gone; this stops "TBD"


def has_section(sections, key):
    return any(_meaningful(body) for heading, body in sections.items()
               if any(heading.startswith(alias) for alias in SECTION_ALIASES[key]))


def issue_kind(issue):
    labels = {name.lower() for name in issue.labels}
    if "bug" in labels:
        return "bug"
    if "spike" in labels:
        return "spike"
    if "bucket" in labels or "(bucket)" in issue.title.lower():
        return "bucket"
    return "feature"


# ── deciding what a rule settles and what the model judges ──────────────────


def plan(issue):
    sections = parse_sections(issue.description)
    kind = issue_kind(issue)
    fixed = {}
    na = set() if kind == "bug" else {"reproduction"}
    if not has_section(sections, "acceptance_criteria"):
        fixed["acceptance_criteria"] = Score(10, "No acceptance criteria (or only the template placeholder).",
                                             BLOCKER_TEXT["acceptance_criteria"], "rule")
    if not has_section(sections, "edge_cases"):
        fixed["edge_cases"] = Score(10, "No edge cases section.", "Document edge cases and failure modes.", "rule")
    if kind == "bug" and not has_section(sections, "reproduction"):
        fixed["reproduction"] = Score(10, "Bug with no reproduction steps.", BLOCKER_TEXT["reproduction"], "rule")
    caps = {dim: CAPS[dim] for dim in ("expected_behavior", "technical_context", "objective")
            if not has_section(sections, dim)}
    if not has_section(sections, "out_of_scope"):
        caps["priority_scope"] = CAPS["out_of_scope"]
    if not issue.priority:
        caps["priority_scope"] = CAPS["priority"]
    if not states_dependencies(issue, sections):
        fixed["dependencies"] = Score(15, "No dependencies named and no linked issues.",
                                      "Name what this depends on or blocks — or write 'Dependencies: none'.", "rule")
    judged = [d for d, _ in DIMENSIONS if d not in fixed and d not in na]
    return Plan(fixed, caps, na, judged)


# ── the judge ───────────────────────────────────────────────────────────────


def build_messages(issue, dims):
    description = issue.description or ""
    truncated = len(description) > MAX_DESCRIPTION_CHARS
    if truncated:
        description = description[:MAX_DESCRIPTION_CHARS] + "\n\n[... description truncated for scoring ...]"
    system = ("You are a strict reviewer deciding whether a coding agent could implement a Linear issue without "
              "guessing. Score each requested dimension 0-100 on this scale: 90 = specific and complete, an agent "
              "needs nothing more; 70 = present but generic or partial; 40 = only mentioned in passing; 10 = "
              "absent. Most real issues sit between 50 and 85 — reserve 90+ for dimensions you could not improve. "
              "For every score of 50 or more, copy a short VERBATIM quote (5-25 words) from the issue that proves "
              "it; a score you cannot support with a quote must be below 50. Judge only what is written. "
              'Reply with JSON only: {"scores": {"<dimension>": {"score": <int 0-100>, "evidence": "<verbatim quote '
              'or empty>", "reason": "<one sentence>", "fix": "<one sentence: what to add>"}}, '
              '"confidence": <int 0-100>}')
    rubric = "\n".join(f"- {d}: {RUBRIC[d]}" for d in dims)
    user = (f"DIMENSIONS_JSON: {json.dumps(dims)}\n\nRubric:\n{rubric}\n\n"
            f"Issue {issue.identifier} (priority field: {issue.priority}, labels: {', '.join(issue.labels) or 'none'})\n"
            f"Title: {issue.title}\n\nDescription:\n{description}")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], truncated


def parse_judgement(text, dims):
    """The model's reply -> ({dim: Score}, confidence). Anything short of a complete, in-range answer is invalid."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(cleaned)
        scores, out = data["scores"], {}
        for dim in dims:
            entry = scores[dim]
            value = entry["score"]
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
                raise ValueError(f"{dim} score {value!r} is not an integer 0-100")
            out[dim] = Score(value, str(entry.get("reason", "")), str(entry.get("fix", "")),
                             evidence=str(entry.get("evidence") or ""))
        confidence = data.get("confidence")
        return out, confidence if isinstance(confidence, int) else None
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise ScorerInvalid(f"judge reply unusable: {e}") from e


def judge(llm, messages, dims):
    """Ask once, retry once on an unusable reply or a transport failure, then give up — never a partial score. A retry
    after an unusable reply shows the judge its reply and what was wrong: at temperature 0 an identical prompt tends to
    reproduce the identical bad reply."""
    last, prompt = None, messages
    for _ in range(2):
        text = None
        try:
            text, model = llm(prompt)
            scores, confidence = parse_judgement(text, dims)
            return scores, confidence, model
        except (ScorerInvalid, ScorerUnavailable) as e:
            last = e
            if text is not None:
                prompt = messages + [{"role": "assistant", "content": text},
                                     {"role": "user", "content": f"That reply was unusable ({e}). Reply again with "
                                                                 f"JSON only, scoring every one of: {json.dumps(dims)}"}]
    raise last


# ── combining ───────────────────────────────────────────────────────────────


def total_of(values):
    values = list(values)
    return int(sum(values) / len(values) + 0.5)


def _verdicts(scores):
    blockers, fixes = [], []
    for dim, s in scores.items():
        if dim in BLOCKER_TEXT and s.score < 40:
            blockers.append(BLOCKER_TEXT[dim])
        elif s.score < 60 and s.fix:
            fixes.append(s.fix)
    return blockers, fixes


def _supported(s, description):
    """A model score >= EVIDENCE_FLOOR stands only if its quote is really in the issue; otherwise it is capped."""
    if s.score > JUDGE_MAX:
        s = Score(JUDGE_MAX, s.reason, s.fix, s.source, s.evidence)
    if s.score < EVIDENCE_FLOOR or quoted(s.evidence, description):
        return s
    return Score(UNSUPPORTED_CAP, f"judge scored {s.score} but its evidence was not found in the issue",
                 s.fix, "rule", s.evidence)


def digest(issue):
    """A fingerprint of everything the score depends on — the sweep re-scores an issue only when it changes."""
    basis = [RUBRIC_VERSION, issue.title, issue.description, issue.priority, sorted(issue.labels), issue.relations]
    return hashlib.sha256(json.dumps(basis).encode()).hexdigest()[:12]


def _median(values):
    return sorted(values)[len(values) // 2]


def vote(llm, messages, dims, description, votes):
    """Judge `votes` times; per dimension keep the MEDIAN (quote-checked) score. At temperature 0 gpt-oss still moved
    up to 4 points between runs and flipped EMA-257 across 80 (83/83/79, 2026-10-06); one outlier vote cannot move a
    median of three. Any vote that fails after its retry fails the whole score — never a median of fewer votes."""
    ballots = [judge(llm, messages, dims) for _ in range(votes)]
    judged = {}
    for dim in dims:
        cast = sorted((_supported(b[0][dim], description) for b in ballots), key=lambda s: s.score)
        judged[dim] = cast[len(cast) // 2]
    confidences = [b[1] for b in ballots if b[1] is not None]
    return judged, (_median(confidences) if confidences else None), ballots[0][2]


def score(issue, llm, votes=1):
    kind = issue_kind(issue)
    if kind == "bucket":
        return Result(issue.identifier, kind, skipped="bucket — its children are scored, not the umbrella")
    p = plan(issue)
    messages, truncated = build_messages(issue, p.judged)
    judged, confidence, model = vote(llm, messages, p.judged, issue.description, votes)
    scores = {}
    for dim, _ in DIMENSIONS:
        if dim in p.na:
            continue
        s = p.fixed.get(dim) or judged[dim]
        if dim in p.caps and s.score > p.caps[dim][0]:
            s = Score(*p.caps[dim], "rule")
        scores[dim] = s
    total = total_of(s.score for s in scores.values())
    blockers, fixes = _verdicts(scores)
    status = "READY" if total >= THRESHOLD and not blockers else "NOT_READY"
    return Result(issue.identifier, kind, scores, p.na, total, status, blockers, fixes, model, confidence, truncated,
                  digest=digest(issue))


# ── output ──────────────────────────────────────────────────────────────────


def _headline(r):
    return f"{'READY' if r.status == 'READY' else 'NOT READY'} · {r.total}/100 (threshold {THRESHOLD})"


def render_comment(r):
    lines = [f"{MARKER} — {_headline(r)}", "", "**Score breakdown**"]
    for dim, _ in DIMENSIONS:
        if dim in r.na:
            lines.append(f"- {LABEL[dim]}: n/a (not a bug)")
        else:
            s = r.scores[dim]
            lines.append(f"- {LABEL[dim]}: {s.score}/100{' (rule)' if s.source == 'rule' else ''} — {s.reason}")
    if r.blockers:
        lines += ["", "**Blockers**"] + [f"- {b}" for b in r.blockers]
    if r.fixes:
        lines += ["", "**Suggested fixes**"] + [f"- {f}" for f in r.fixes]
    if r.truncated:
        lines += ["", f"Note: the description was truncated to {MAX_DESCRIPTION_CHARS} characters for scoring."]
    conf = f" · confidence {r.confidence}%" if r.confidence is not None else ""
    lines += ["", f"_weyland issue-readiness · rubric v{RUBRIC_VERSION} · model {r.model}{conf} · "
                  f"digest {r.digest} · re-run: `scripts/issue-readiness.sh {r.identifier}`_"]
    return "\n".join(lines)


def render_text(r):
    if r.skipped:
        return f"{r.identifier}  SKIPPED  {r.skipped}"
    out = [f"{r.identifier}  {_headline(r)}  model={r.model} rubric v{RUBRIC_VERSION}"]
    for dim, _ in DIMENSIONS:
        if dim in r.na:
            out.append(f"  {dim:<20} n/a")
        else:
            s = r.scores[dim]
            out.append(f"  {dim:<20} {s.score:>3}  {s.source:<4} {s.reason}")
    out += [f"  BLOCKER: {b}" for b in r.blockers] + [f"  fix: {f}" for f in r.fixes]
    if r.truncated:
        out.append(f"  note: description truncated to {MAX_DESCRIPTION_CHARS} chars")
    return "\n".join(out)


def render_json(r):
    return json.dumps({
        "identifier": r.identifier, "kind": r.kind, "skipped": r.skipped, "total": r.total, "status": r.status,
        "scores": {d: {"score": s.score, "reason": s.reason, "source": s.source} for d, s in r.scores.items()},
        "na": sorted(r.na), "blockers": r.blockers, "fixes": r.fixes, "model": r.model,
        "confidence": r.confidence, "rubric": RUBRIC_VERSION, "truncated": r.truncated,
    })


def our_comment(linear, issue_uuid):
    """The scorer's own comment on an issue (our user + MARKER), or None."""
    me = linear.viewer_id()
    return next((c for c in linear.comments_on(issue_uuid) if c["user"] == me and MARKER in c["body"]), None)


def upsert_comment(linear, issue_uuid, body):
    c = our_comment(linear, issue_uuid)
    if c is None:
        linear.create_comment(issue_uuid, body)
        return "created"
    if c["body"].strip() == body.strip():
        return "unchanged"
    linear.update_comment(c["id"], body)
    return "updated"


# ── clients ─────────────────────────────────────────────────────────────────


RATE_LIMIT_TRIES = 4                   # one call + 3 backed-off retries on HTTP 429
RATE_LIMIT_WAIT = 20                   # seconds, when the server sends no Retry-After


def _retry_after(e):
    try:
        return max(1, int(e.headers.get("Retry-After") or RATE_LIMIT_WAIT))
    except (TypeError, ValueError):
        return RATE_LIMIT_WAIT


def _post_json(url, payload, headers, timeout, error, with_headers=False):
    """POST JSON. A 429 (rate limit) is backed off and retried; still limited after RATE_LIMIT_TRIES, or any other
    failure, raises `error` — the caller never gets a partial answer."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    for attempt in range(RATE_LIMIT_TRIES):
        try:
            return _send(req, timeout, with_headers)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == RATE_LIMIT_TRIES - 1:
                raise error(f"HTTP {e.code} from {url}") from e
            time.sleep(_retry_after(e))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise error(f"{url}: {e}") from e


def _send(req, timeout, with_headers):
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.load(resp)
        return (body, {k.lower(): v for k, v in resp.headers.items()}) if with_headers else body


def litellm_client(env):
    key = env.get("LITELLM_API_KEY")
    if not key:
        raise ScorerUnavailable("LITELLM_API_KEY is not set")
    base = env.get("LITELLM_API_BASE", "http://192.168.1.243:30400").rstrip("/")
    url = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
    model = env.get("ISSUE_READINESS_MODEL", DEFAULT_MODEL)

    payload = {"model": model, "temperature": 0, "seed": 0, "response_format": {"type": "json_object"}}
    if env.get("ISSUE_READINESS_NO_FALLBACKS") == "1":        # judge eval: the answer must come from THIS model
        payload["disable_fallbacks"] = True

    def call(messages):
        data, headers = _post_json(url, {**payload, "messages": messages},
                                   {"Authorization": f"Bearer {key}"}, 300, ScorerUnavailable, with_headers=True)
        try:
            return data["choices"][0]["message"]["content"], answered_by(data, headers, model)
        except (KeyError, IndexError, TypeError) as e:
            raise ScorerInvalid(f"gateway reply has no message: {e}") from e
    return call


def answered_by(data, headers, alias):
    """Which model really answered. LiteLLM echoes the ALIAS as `model`; the backend and whether a fallback fired are
    only in its x-litellm-* headers (observed live 2026-10-06, LiteLLM 1.93.0)."""
    name = data.get("model") or alias
    if "x-litellm-model-api-base" not in headers:          # not behind LiteLLM (e.g. Ollama directly, for calibration)
        return name
    return (f"{name} @ {headers['x-litellm-model-api-base']} "
            f"(fallbacks {headers.get('x-litellm-attempted-fallbacks', '?')})")


class Linear:
    def __init__(self, key):
        if not key:
            raise LinearError("LINEAR_API_KEY is not set")
        self.key = key

    def q(self, query, **variables):
        data = _post_json(LINEAR_URL, {"query": query, "variables": variables},
                          {"Authorization": self.key}, 60, LinearError)
        if data.get("errors"):
            raise LinearError(data["errors"][0].get("message", "GraphQL error"))
        return data["data"]

    @staticmethod
    def _issue(n):
        return Issue(n["identifier"], n["id"], n["title"], n.get("description") or "", n.get("priority") or 0,
                     [lb["name"] for lb in n["labels"]["nodes"]], (n.get("project") or {}).get("name"),
                     len(n["relations"]["nodes"]) + len(n["inverseRelations"]["nodes"]))

    FIELDS = ("id identifier title description priority labels { nodes { name } } project { name } "
              "relations { nodes { id } } inverseRelations { nodes { id } }")

    def issue(self, identifier):
        return self._issue(self.q(f"query($id:String!){{issue(id:$id){{{self.FIELDS}}}}}", id=identifier)["issue"])

    def open_high(self, project):
        d = self.q("query($p:String!){issues(first:100,filter:{project:{name:{eq:$p}},priority:{eq:2},"
                   f"state:{{type:{{nin:[\"completed\",\"canceled\"]}}}}}}){{nodes{{{self.FIELDS}}}}}}}", p=project)
        return [self._issue(n) for n in d["issues"]["nodes"]]

    def viewer_id(self):
        return self.q("query{viewer{id}}")["viewer"]["id"]

    def comments_on(self, issue_uuid):
        d = self.q("query($id:String!){issue(id:$id){comments(first:100){nodes{id body user{id}}}}}", id=issue_uuid)
        return [{"id": c["id"], "body": c["body"], "user": (c.get("user") or {}).get("id")}
                for c in d["issue"]["comments"]["nodes"]]

    def create_comment(self, issue_uuid, body):
        self.q("mutation($i:String!,$b:String!){commentCreate(input:{issueId:$i,body:$b}){success}}",
               i=issue_uuid, b=body)

    def update_comment(self, comment_id, body):
        self.q("mutation($c:String!,$b:String!){commentUpdate(id:$c,input:{body:$b}){success}}", c=comment_id, b=body)


# ── CLI ─────────────────────────────────────────────────────────────────────


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def _args(argv):
    ap = _Parser(prog="issue-readiness", description="Score a Linear issue's readiness for a coding agent.")
    ap.add_argument("identifier", nargs="?", help="Linear issue id, e.g. EMA-249")
    ap.add_argument("--issue-file", help="score a saved issue (JSON with the Issue fields) instead of fetching one")
    ap.add_argument("--sweep", action="store_true", help=f"score every open High issue in project {SWEEP_PROJECT}")
    ap.add_argument("--no-comment", action="store_true", help="do not write the Linear comment")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    ap.add_argument("--votes", type=int, default=DEFAULT_VOTES, help="judgements per score (median per dimension)")
    args = ap.parse_args(argv)
    if sum(bool(x) for x in (args.identifier, args.issue_file, args.sweep)) != 1:
        raise UsageError("give exactly one of: an issue id, --issue-file, --sweep")
    if args.issue_file and not args.no_comment:
        raise UsageError("--issue-file has no Linear issue to comment on; add --no-comment")
    return args


def _issues(args, linear):
    if args.issue_file:
        with open(args.issue_file) as f:
            return [Issue(**json.load(f))]
    if args.sweep:
        return linear.open_high(SWEEP_PROJECT)
    return [linear.issue(args.identifier)]


def _unchanged(args, linear, iss):
    """Sweep only: the issue's last score was of exactly this content, so scoring again would change nothing."""
    if not args.sweep or args.no_comment:
        return False
    c = our_comment(linear, iss.uuid)
    return c is not None and f"digest {digest(iss)}" in c["body"]


def _run(args, llm, linear):
    worst = 0
    for iss in _issues(args, linear):
        if _unchanged(args, linear, iss):
            print(f"{iss.identifier}  unchanged since last score (digest {digest(iss)})")
            continue
        r = score(iss, llm, args.votes)
        print(render_json(r) if args.json else render_text(r))
        if r.skipped:
            continue
        if not args.no_comment:
            print(f"  comment: {upsert_comment(linear, iss.uuid, render_comment(r))}", file=sys.stderr)
        worst = max(worst, 0 if r.status == "READY" else 1)
    return worst


def main(argv=None, llm=None, linear=None, env=None):
    env = os.environ if env is None else env
    try:
        args = _args(sys.argv[1:] if argv is None else argv)
        if linear is None and not (args.issue_file and args.no_comment):
            linear = Linear(env.get("LINEAR_API_KEY"))
        return _run(args, llm or litellm_client(env), linear)
    except UsageError as e:
        print(f"issue-readiness: usage: {e}", file=sys.stderr)
    except ScorerUnavailable as e:
        print(f"issue-readiness: scorer unavailable — {e}", file=sys.stderr)
    except ScorerInvalid as e:
        print(f"issue-readiness: scorer invalid — {e}", file=sys.stderr)
    except LinearError as e:
        print(f"issue-readiness: linear unavailable — {e}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
