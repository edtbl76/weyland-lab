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
WHY = ("Why", ("why", "problem", "purpose", PREAMBLE))
TECH = ("Technical context", ("technical context",))
AC = ("Acceptance criteria", ("acceptance criteria",))
EDGE = ("Edge cases & failure modes", ("edge cases",))
OOS = ("Out of scope", ("out of scope", "in scope / out of scope"))
REQUIRED = {
    "backlog item": [WHY, ("Scope", ("scope", "in scope")), TECH, AC, EDGE, OOS],
    "bug": [("Observed", ("observed",)), ("Expected", ("expected",)), ("Repro", ("repro", "steps to reproduce")),
            ("Evidence", ("evidence",)), TECH, AC, EDGE],
    "spike": [("Questions to answer", ("questions to answer",)), ("Constraint gate", ("constraint gate",)),
              ("Overlap", ("overlap",)), TECH, AC, EDGE, OOS, ("Deliverable", ("deliverable",))],
    "bucket": [("Purpose", ("purpose", PREAMBLE)), ("Exit criteria", ("exit criteria",))],
}
TEMPLATE = {"backlog item": "Backlog item", "bug": "Bug", "spike": "Spike", "bucket": "Bucket"}

# Guidance the templates pre-fill — a section holding only these is still empty.
TEMPLATE_GUIDANCE = (
    "testable, pass/fail", "what breaks, what's absent", "affected systems, files, services",
    "the regression test fails on the bug", "| where | what | role |", "| -- | -- | -- |", "(host / repo)",
    "logs, ids, the exact command run", "what the lab already runs that covers this",
    "$0 — free forever, not a trial", "sub-issues — each with its own kind",
    "when this bucket is done, even if follow-ons remain",
    "what it actually is", "a verdict + rationale in",          # the Spike template pre-fills these two
)
PLACEHOLDER_LINE = re.compile(r"^\s*([-*]\s*(\[[ xX]\])?\s*)?(\([^)]*\))?\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s*)?(?P<text>\S.*)$")
HEADING = re.compile(r"^#{1,4}\s+(?P<h>.*?)\s*#*\s*$")
# A bold run that OPENS a line and is short is a pseudo-heading ("**Why.** It broke." / "**Acceptance criteria**");
# bold mid-sentence is emphasis, not a section.
BOLD_HEADING = re.compile(r"^\*\*(?P<h>[^*\n]{2,48}?)[.:]?\*\*[.:]?\s*(?P<rest>.*)$")


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
    project: str = None


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
        m = HEADING.match(line) or BOLD_HEADING.match(line)
        if m:
            current = m.group("h").strip().rstrip(".:").lower()
            sections[current] = (m.groupdict().get("rest") or "") + "\n"
        else:
            sections[current] += line + "\n"
    if not sections[PREAMBLE].strip():
        del sections[PREAMBLE]
    return sections


def _content_lines(body):
    return [ln for ln in body.splitlines()
            if not PLACEHOLDER_LINE.match(ln) and not any(g in ln.lower() for g in TEMPLATE_GUIDANCE)]


PLACEHOLDER_WORDS = {"tbd", "tba", "todo", "wip", "n/a", "na", "xxx", "...", "?", "-"}


def _meaningful(body):
    """Real content, not just the template's guidance, placeholders or a stand-in word ("TBD")."""
    words = [re.sub(r"^[-*+]\s*|^\d+[.)]\s*", "", ln).strip().lower().rstrip(".") for ln in _content_lines(body)]
    real = [w for w in words if w and w not in PLACEHOLDER_WORDS]
    return len(re.findall(r"[A-Za-z0-9]", " ".join(real))) >= 2


def _has_criterion(body):
    """At least one list item that is a real criterion — prose alone is not a pass/fail check."""
    return any(LIST_ITEM.match(ln) and _meaningful(ln) for ln in _content_lines(body))


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
    return "backlog item"


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
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
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
