#!/usr/bin/env python3
"""Issue readiness — does a Linear issue meet the lab's implementation-ready standard? (B190, replaces SpecBot)

The job: AGENTS.md requires every issue an agent drafts to be implementation-ready — beyond Why and Scope it carries
Technical context, Acceptance criteria, Edge cases & failure modes and Out of scope — and to be checked before it is
delegated. SpecBot did that check (25 a month, cloud-only, no CI gate). The standard is written down per issue kind in
the Linear templates, so this checks it EXACTLY, by rule: every required section present and not just the template's
placeholder, at least one real acceptance criterion, the priority field set. READY or NOT READY, and every missing item
named. No model and no score: an LLM 0-100 readiness score was built and dropped on evidence — on 200 issues with known
agent outcomes no text-based readiness score predicted success (AUC ~0.51; docs/concepts/issue-readiness.md).

Exit codes:  0 READY (or every swept issue READY)  ·  1 NOT READY  ·  2 Linear unavailable / usage — never READY.

  issue_readiness.py EMA-249                 check one issue and create/update its one comment
  issue_readiness.py EMA-249 --no-comment    check only (--json for machine-readable)
  issue_readiness.py --sweep                 every open High issue in project Weyland Lab (the lean-CI step)

Env: LINEAR_API_KEY (write scope to comment; read is enough with --no-comment). Runbook: docs/runbooks/issue-readiness.md.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

MARKER = "**Issue readiness (weyland check)**"
LEGACY_MARKERS = ("**Issue readiness (weyland scorer)**",)   # the dropped 0-100 scorer's comments are taken over
SWEEP_PROJECT = "Weyland Lab"
LINEAR_URL = os.environ.get("ISSUE_READINESS_LINEAR_URL", "https://api.linear.app/graphql")   # override: tests
PRIORITY_ITEM = "Priority (the issue's priority field)"
PREAMBLE = "(opening paragraph)"        # text before the first heading — EMA-240 / EMA-243 state their problem there

# The standard, per issue kind: the content sections of the Linear template of that kind (Backlog item / Bug / Spike /
# Bucket), which AGENTS.md § "Every issue an agent drafts is implementation-ready" mandates. (display name, headings
# that count — a heading counts when it STARTS with one of these, so "Edge cases" satisfies "Edge cases & failure
# modes".) The templates' closing "Backlog" / "Fix + regression test" / "Priority rule" sections are instructions,
# not content, and are not required. Keep in step with the templates when either changes.
BACKLOG_ITEM = "backlog item"           # the default kind
WHY = ("Why", ("why", "problem", "purpose", PREAMBLE))
TECH = ("Technical context", ("technical context",))
AC = ("Acceptance criteria", ("acceptance criteria",))
EDGE = ("Edge cases & failure modes", ("edge cases",))
OOS = ("Out of scope", ("out of scope", "in scope / out of scope"))
REQUIRED = {
    BACKLOG_ITEM: [WHY, ("Scope", ("scope", "in scope")), TECH, AC, EDGE, OOS],
    "bug": [("Observed", ("observed",)), ("Expected", ("expected",)), ("Repro", ("repro", "steps to reproduce")),
            ("Evidence", ("evidence",)), TECH, AC, EDGE],
    "spike": [("Questions to answer", ("questions to answer",)), ("Constraint gate", ("constraint gate",)),
              ("Overlap", ("overlap",)), TECH, AC, EDGE, OOS, ("Deliverable", ("deliverable",))],
    "bucket": [("Purpose", ("purpose", PREAMBLE)), ("Exit criteria", ("exit criteria",))],
}
TEMPLATE = {BACKLOG_ITEM: "Backlog item", "bug": "Bug", "spike": "Spike", "bucket": "Bucket"}

# The guidance lines the Linear templates pre-fill, WHOLE (normalized: list marker / checkbox stripped, lowercase,
# whitespace collapsed). A line is guidance only if it IS one of these or a trimmed piece of one; a line that merely
# QUOTES template wording and adds real content counts (2026-10-07: matching phrases anywhere in a line dropped
# "A verdict + rationale in docs/concepts/: DON'T ADOPT, because ..." as empty). Keep in step with the templates.
TEMPLATE_GUIDANCE = (
    "testable, pass/fail — each one a check someone (or an agent) can run.",
    "what breaks, what's absent, what fails closed.",
    "affected systems, files, services and apis — host, path, role in this change.",
    "affected systems, files, services and apis.",
    "| where | what | role |", "| -- | -- | -- |",
    "| (host / repo) | (path or service) | (changed / read / retired) |",
    "| (host / repo) | (path or service) | (changed / read) |",
    "the regression test fails on the bug and passes on the fix.",
    "logs, ids, the exact command run and its output (an exit code is not a verdict).",
    "what the lab already runs that covers this.",
    "$0 — free forever, not a trial (cloud is fine if free). check this first.",
    "what it actually is",
    "a verdict + rationale in `docs/concepts/`. don't adopt → one paragraph why; adopt → a bounded plan.",
    "sub-issues — each with its own kind and b-number.",
    "when this bucket is done, even if follow-ons remain (move those to new items).",
)
CHECKBOXES = ("[ ]", "[x]", "[X]")


# Line parsing is plain string handling, not regular expressions: issue text is untrusted input, and the regex forms
# these replaced were flagged for polynomial backtracking (SonarQube hotspots, CI #279).


def heading_of(line):
    """(heading text, rest of the line) for a `#`-`####` heading or a line-opening short bold run, else None.
    A bold run that OPENS a line and is 2-48 chars is a pseudo-heading ("**Why.** It broke." / "**Acceptance
    criteria**"); bold mid-sentence is emphasis, not a section."""
    if line.startswith("#"):
        level = len(line) - len(line.lstrip("#"))
        if 1 <= level <= 4 and line[level:level + 1] in (" ", "\t"):
            text = line[level:].strip().rstrip("#").strip()
            return (text, "") if text else None
        return None
    if line.startswith("**"):
        end = line.find("**", 2)
        text = line[2:end] if end > 2 else ""
        if not 2 <= len(text) <= 48 or "*" in text:
            return None
        rest = line[end + 2:]
        rest = rest[1:] if rest[:1] in (".", ":") else rest
        return text.rstrip(".:").strip(), rest.strip()
    return None


def _strip_marker(line):
    """The text of a list item (`- `, `* `, `+ `, `1. `, `1) `, with an optional checkbox), or None if not one."""
    s = line.lstrip()
    if s[:1] in ("-", "*", "+") and s[1:2] in (" ", "\t"):
        s = s[2:]
    else:
        digits = len(s) - len(s.lstrip("0123456789"))
        if not digits or s[digits:digits + 1] not in (".", ")") or s[digits + 1:digits + 2] not in (" ", "\t"):
            return None
        s = s[digits + 2:]
    s = s.lstrip()
    for box in CHECKBOXES:
        if s.startswith(box):
            s = s[len(box):].lstrip()
    return s


def _is_placeholder(line):
    """Blank, a bare bullet / checkbox, or only a `(parenthesised placeholder)` — the template's empty slots."""
    s = line.strip()
    item = _strip_marker(s) if s[:1] in ("-", "*") else s
    rest = (item if item is not None else s).strip()
    return not rest or (rest.startswith("(") and rest.endswith(")") and ")" not in rest[1:-1])


class LinearError(Exception):
    """Linear could not be read or written."""


class UsageError(Exception):
    pass


@dataclass
class Issue:
    identifier: str
    uuid: str
    title: str
    description: str
    priority: int                       # Linear native field: 0 none, 1 urgent, 2 high, 3 medium, 4 low
    labels: list = field(default_factory=list)
    project: Optional[str] = None


@dataclass
class Result:
    identifier: str
    kind: str
    missing: list

    @property
    def ready(self):
        return not self.missing


# ── reading the issue ───────────────────────────────────────────────────────


def parse_sections(markdown):
    """{lowercased heading text: body} for `#` headings and line-opening bold pseudo-headings; text before the first
    heading is kept under PREAMBLE."""
    sections, current = {PREAMBLE: ""}, PREAMBLE
    for line in (markdown or "").splitlines():
        h = heading_of(line)
        if h:
            current = h[0].rstrip(".:").lower()
            sections[current] = h[1] + "\n"
        else:
            sections[current] += line + "\n"
    if not sections[PREAMBLE].strip():
        del sections[PREAMBLE]
    return sections


def _normalized(line):
    return " ".join((_strip_marker(line) or line).lower().split())


def _is_guidance(line):
    text = _normalized(line)
    return bool(text) and any(text == g or text in g for g in TEMPLATE_GUIDANCE)


def _content_lines(body):
    return [ln for ln in body.splitlines() if not _is_placeholder(ln) and not _is_guidance(ln)]


PLACEHOLDER_WORDS = {"tbd", "tba", "todo", "wip", "n/a", "na", "xxx", "...", "?", "-"}


def _meaningful(body):
    """Real content, not just the template's guidance, placeholders or a stand-in word ("TBD")."""
    words = [(_strip_marker(ln) or ln).strip().lower().rstrip(".") for ln in _content_lines(body)]
    real = [w for w in words if w and w not in PLACEHOLDER_WORDS]
    return len(re.findall(r"[A-Za-z0-9]", " ".join(real))) >= 2


def _has_criterion(body):
    """At least one list item that is a real criterion — prose alone is not a pass/fail check."""
    return any(_strip_marker(ln) and _meaningful(ln) for ln in _content_lines(body))


def _bodies(sections, aliases):
    return [body for heading, body in sections.items() if any(heading.startswith(a) for a in aliases)]


def issue_kind(issue):
    labels = {name.lower() for name in issue.labels}
    if "bug" in labels:
        return "bug"
    if "spike" in labels:
        return "spike"
    if "bucket" in labels or "(bucket)" in issue.title.lower():
        return "bucket"
    return BACKLOG_ITEM


def check(issue):
    sections, kind = parse_sections(issue.description), issue_kind(issue)
    missing = []
    for name, aliases in REQUIRED[kind]:
        bodies = _bodies(sections, aliases)
        good = _has_criterion if (name, aliases) == AC else _meaningful
        if not any(good(b) for b in bodies):
            missing.append(name)
    if not issue.priority:
        missing.append(PRIORITY_ITEM)
    return Result(issue.identifier, kind, missing)


# ── output ──────────────────────────────────────────────────────────────────


def _standard(r):
    return f"AGENTS.md's implementation-ready standard (Linear template \"{TEMPLATE[r.kind]}\")"


def render_comment(r):
    if r.ready:
        lines = [f"{MARKER} — READY", "", f"Every section required by {_standard(r)} is present."]
    else:
        lines = [f"{MARKER} — NOT READY", "", f"Missing for {_standard(r)}:"] + [f"- {m}" for m in r.missing]
        lines += ["", "A section counts when it has real content, not just the template's guidance; acceptance "
                      "criteria need at least one checkbox or bullet."]
    lines += ["", f"_re-run: `scripts/issue-readiness.sh {r.identifier}`_"]
    return "\n".join(lines)


def render_text(r):
    head = f"{r.identifier}  {'READY' if r.ready else 'NOT READY'}  ({TEMPLATE[r.kind]})"
    return "\n".join([head] + [f"  missing: {m}" for m in r.missing])


def render_json(r):
    return json.dumps({"identifier": r.identifier, "kind": r.kind, "ready": r.ready, "missing": r.missing})


def upsert_comment(linear, issue_uuid, body):
    """ONE comment per issue: ours = our user + MARKER. Updated in place; an unchanged result writes nothing."""
    me = linear.viewer_id()
    c = next((c for c in linear.comments_on(issue_uuid)
              if c["user"] == me and any(m in c["body"] for m in (MARKER,) + LEGACY_MARKERS)), None)
    if c is None:
        linear.create_comment(issue_uuid, body)
        return "created"
    if c["body"].strip() == body.strip():
        return "unchanged"
    linear.update_comment(c["id"], body)
    return "updated"


# ── Linear ──────────────────────────────────────────────────────────────────

RATE_LIMIT_TRIES = 4                   # one call + 3 backed-off retries on HTTP 429
RATE_LIMIT_WAIT = 20                   # seconds, when Linear sends no Retry-After


def _retry_after(e):
    try:
        return max(1, int(e.headers.get("Retry-After") or RATE_LIMIT_WAIT))
    except (TypeError, ValueError):
        return RATE_LIMIT_WAIT


def _post_json(url, payload, headers, timeout):
    """POST JSON. A 429 is backed off and retried; still limited after RATE_LIMIT_TRIES, or any other failure, raises
    LinearError — the caller never acts on a partial answer."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):   # the URL can come from env: never file:// etc.
        raise LinearError(f"refusing URL scheme of {url!r}")
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    for attempt in range(RATE_LIMIT_TRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 nosemgrep -- scheme checked above
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == RATE_LIMIT_TRIES - 1:
                raise LinearError(f"HTTP {e.code} from {url}") from e
            time.sleep(_retry_after(e))
        except (OSError, ValueError) as e:     # URLError and TimeoutError are OSErrors
            raise LinearError(f"{url}: {e}") from e


class Linear:
    FIELDS = "id identifier title description priority labels { nodes { name } } project { name }"

    def __init__(self, key):
        if not key:
            raise LinearError("LINEAR_API_KEY is not set")
        self.key = key

    def q(self, query, **variables):
        data = _post_json(LINEAR_URL, {"query": query, "variables": variables}, {"Authorization": self.key}, 60)
        if data.get("errors"):
            raise LinearError(data["errors"][0].get("message", "GraphQL error"))
        return data["data"]

    @staticmethod
    def _issue(n):
        return Issue(n["identifier"], n["id"], n["title"], n.get("description") or "", n.get("priority") or 0,
                     [lb["name"] for lb in n["labels"]["nodes"]], (n.get("project") or {}).get("name"))

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


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def _args(argv):
    ap = _Parser(prog="issue-readiness", description="Check a Linear issue against the implementation-ready standard.")
    ap.add_argument("identifier", nargs="?", help="Linear issue id, e.g. EMA-249")
    ap.add_argument("--sweep", action="store_true", help=f"every open High issue in project {SWEEP_PROJECT}")
    ap.add_argument("--no-comment", action="store_true", help="do not write the Linear comment")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = ap.parse_args(argv)
    if bool(args.identifier) == args.sweep:
        raise UsageError("give an issue id or --sweep")
    return args


def _run(args, linear):
    issues = linear.open_high(SWEEP_PROJECT) if args.sweep else [linear.issue(args.identifier)]
    worst = 0
    for iss in issues:
        r = check(iss)
        print(render_json(r) if args.json else render_text(r), flush=True)
        if not args.no_comment:
            print(f"  comment: {upsert_comment(linear, iss.uuid, render_comment(r))}", file=sys.stderr, flush=True)
        worst = max(worst, 0 if r.ready else 1)
    return worst


def main(argv=None, linear=None, env=None):
    env = os.environ if env is None else env
    try:
        args = _args(sys.argv[1:] if argv is None else argv)
        return _run(args, linear or Linear(env.get("LINEAR_API_KEY")))
    except UsageError as e:
        print(f"issue-readiness: usage: {e}", file=sys.stderr)
    except LinearError as e:
        print(f"issue-readiness: linear unavailable — {e}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
