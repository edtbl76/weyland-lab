"""Tests for issue_readiness.py — the check that replaces SpecBot (B190, rewritten 2026-10-06).

SpecBot's job in this lab was enforcing AGENTS.md's implementation-ready standard before an issue is delegated: beyond
Why and Scope, every drafted issue carries Technical context, Acceptance criteria, Edge cases & failure modes and Out of
scope. That standard is written down per issue kind (the Linear templates), so it is checked exactly, by rule — no
judge, no score. (An LLM quality score was built and dropped: no text-based readiness score predicted agent outcomes —
docs/concepts/issue-readiness.md.) These pin every decision; Linear is a fake object, nothing leaves the process.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import issue_readiness as ir

BACKLOG_ITEM = """## Why

The nightly backup has no restore drill, so nobody knows whether it restores.

## Scope

Add a drill job and document it.

## Technical context

| Where | What | Role |
| -- | -- | -- |
| mother | k8s/foo/backup.yaml | changed |

## Acceptance criteria

- [ ] The drill restores the newest backup read-only and prints its row counts.

## Edge cases & failure modes

* An empty backup directory exits 2.

## Out of scope

* Off-site copies.
"""

BUG = """## Observed

The sweep exits 0 when Linear is down.

## Expected

Exit 2.

## Repro

1. Block api.linear.app. 2. Run the sweep.

## Evidence

`exit=0` in pipeline #999.

## Technical context

`scripts/issue_readiness.py` on rogueone.

## Acceptance criteria

- [ ] The sweep exits 2 with Linear blocked.

## Edge cases & failure modes

* A 429 is retried first.
"""


def issue(description=BACKLOG_ITEM, priority=2, labels=(), title="B999 — Restore drill"):
    return ir.Issue("EMA-999", "u-999", title, description, priority, list(labels), "Weyland Lab")


# ── kinds and their standard ────────────────────────────────────────────────


def test_kind_comes_from_labels_then_title():
    assert ir.issue_kind(issue(labels=["Bug"])) == "bug"
    assert ir.issue_kind(issue(labels=["Spike"])) == "spike"
    assert ir.issue_kind(issue(title="B78 — Data-mesh maturity (bucket)")) == "bucket"
    assert ir.issue_kind(issue()) == "backlog item"


def test_every_kind_requires_what_agents_md_names():
    # AGENTS.md: "beyond Why/Scope it carries Technical context, Acceptance criteria, Edge cases & failure modes,
    # and Out of scope" — every kind an agent implements must demand those (Bug: Out of scope is not in its template).
    for kind in ("backlog item", "spike"):
        names = {name for name, _ in ir.REQUIRED[kind]}
        assert {"Technical context", "Acceptance criteria", "Edge cases & failure modes", "Out of scope"} <= names
    assert {"Technical context", "Acceptance criteria", "Edge cases & failure modes"} <= {n for n, _ in ir.REQUIRED["bug"]}


def test_a_complete_backlog_item_is_ready():
    r = ir.check(issue())
    assert r.ready and r.missing == []


def test_a_complete_bug_is_ready():
    assert ir.check(issue(BUG, labels=["Bug"])).ready


def test_each_missing_section_is_named():
    desc = BACKLOG_ITEM.split("## Technical context")[0] + "## Acceptance criteria" + \
        BACKLOG_ITEM.split("## Acceptance criteria")[1].split("## Out of scope")[0]
    r = ir.check(issue(desc))
    assert not r.ready
    assert r.missing == ["Technical context", "Out of scope"]


def test_an_empty_description_lists_every_section():
    r = ir.check(issue(""))
    assert [m for m in r.missing] == [name for name, _ in ir.REQUIRED["backlog item"]]


# ── what counts as present ──────────────────────────────────────────────────


def test_a_heading_with_only_the_template_guidance_is_missing():
    desc = BACKLOG_ITEM.replace("* An empty backup directory exits 2.",
                                "What breaks, what's absent, what fails closed.\n\n* (edge case)")
    assert ir.check(issue(desc)).missing == ["Edge cases & failure modes"]


def test_acceptance_criteria_need_one_real_criterion_not_prose_or_placeholder():
    placeholder = BACKLOG_ITEM.replace(
        "- [ ] The drill restores the newest backup read-only and prints its row counts.",
        "Testable, pass/fail — each one a check someone (or an agent) can run.\n\n- [ ] (criterion)")
    assert "Acceptance criteria" in ir.check(issue(placeholder)).missing
    prose = BACKLOG_ITEM.replace("- [ ] The drill restores the newest backup read-only and prints its row counts.",
                                 "It should work well once the drill exists.")
    assert "Acceptance criteria" in ir.check(issue(prose)).missing


def test_bold_pseudo_headings_and_heading_variants_count():
    desc = ("**Why.** It broke last night.\n\n**Scope**\nAdd a drill.\n\n**Technical context**\n`k8s/foo.yaml`\n\n"
            "**Acceptance criteria**\n- [ ] the drill prints row counts\n\n**Edge cases**\n* empty dir exits 2\n\n"
            "**Out of scope**\n* off-site copies\n")
    assert ir.check(issue(desc)).ready


def test_an_opening_paragraph_counts_as_the_why():
    # EMA-240 / EMA-243 open with the problem and only then start headings
    desc = "The lab has no time tracking, so nobody knows where the hours go.\n\n## Scope" + \
        BACKLOG_ITEM.split("## Scope", 1)[1]
    assert ir.check(issue(desc)).ready


def test_bold_text_inside_a_sentence_is_not_a_heading():
    s = ir.parse_sections("## Why\n\nThis is **really** broken and **must** be fixed today.\n")
    assert list(s) == ["why"]


def test_a_bucket_is_checked_against_the_bucket_template():
    bucket = "## Purpose\n\nGroup the mesh work.\n\n## Exit criteria\n\nAll children done.\n"
    r = ir.check(issue(bucket, title="B78 — Data-mesh maturity (bucket)"))
    assert r.ready and r.kind == "bucket"
    assert ir.check(issue("## Purpose\n\nGroup it.\n", title="B78 — x (bucket)")).missing == ["Exit criteria"]


def test_no_priority_is_named():
    assert ir.check(issue(priority=0)).missing == ["Priority (the issue's priority field)"]


# ── output ──────────────────────────────────────────────────────────────────


def test_comment_names_the_standard_and_every_missing_item():
    r = ir.check(issue(priority=0))
    body = ir.render_comment(r)
    assert body.startswith(ir.MARKER) and "NOT READY" in body
    assert "Priority" in body and "AGENTS.md" in body and "Backlog item" in body


def test_ready_comment_says_ready():
    assert "READY" in ir.render_comment(ir.check(issue())) and "NOT READY" not in ir.render_comment(ir.check(issue()))


class FakeLinear:
    def __init__(self, comments=(), issues=()):
        self.comments = [dict(c) for c in comments]
        self.issues = list(issues)
        self.writes = []

    def viewer_id(self):
        return "me"

    def comments_on(self, issue_uuid):
        return self.comments

    def create_comment(self, issue_uuid, body):
        self.writes.append(("create", body))

    def update_comment(self, comment_id, body):
        self.writes.append(("update", comment_id, body))

    def issue(self, identifier):
        return self.issues[0]

    def open_high(self, project):
        return self.issues


def test_first_check_creates_one_comment():
    lin = FakeLinear()
    assert ir.upsert_comment(lin, "u", f"{ir.MARKER} x") == "created"


def test_rechecking_updates_the_same_comment():
    lin = FakeLinear([{"id": "c1", "body": f"{ir.MARKER} old", "user": "me"}])
    assert ir.upsert_comment(lin, "u", f"{ir.MARKER} new") == "updated"
    assert lin.writes == [("update", "c1", f"{ir.MARKER} new")]


def test_an_unchanged_result_writes_nothing():
    lin = FakeLinear([{"id": "c1", "body": f"{ir.MARKER} same", "user": "me"}])
    assert ir.upsert_comment(lin, "u", f"{ir.MARKER} same") == "unchanged" and not lin.writes


def test_someone_elses_comment_with_the_marker_is_not_ours():
    lin = FakeLinear([{"id": "c9", "body": f"quoting {ir.MARKER}", "user": "someone"}])
    assert ir.upsert_comment(lin, "u", f"{ir.MARKER} x") == "created"


# ── CLI ─────────────────────────────────────────────────────────────────────


def test_cli_ready_exits_0_and_comments(capsys):
    lin = FakeLinear(issues=[issue()])
    assert ir.main(["EMA-999"], linear=lin) == 0
    assert "READY" in capsys.readouterr().out and lin.writes[0][0] == "create"


def test_cli_not_ready_exits_1_naming_what_is_missing(capsys):
    assert ir.main(["EMA-999", "--no-comment"], linear=FakeLinear(issues=[issue(priority=0)])) == 1
    assert "Priority" in capsys.readouterr().out


def test_sweep_reports_the_worst(capsys):
    lin = FakeLinear(issues=[issue(), issue(priority=0)])
    assert ir.main(["--sweep", "--no-comment"], linear=lin) == 1


def test_linear_unavailable_is_exit_2_never_ready(capsys):
    class Down(FakeLinear):
        def issue(self, identifier):
            raise ir.LinearError("HTTP 503 from https://api.linear.app/graphql")
    assert ir.main(["EMA-999"], linear=Down()) == 2
    assert "linear unavailable" in capsys.readouterr().err


def test_no_issue_is_a_usage_error(capsys):
    assert ir.main([], linear=FakeLinear()) == 2


def test_json_output(capsys):
    ir.main(["EMA-999", "--no-comment", "--json"], linear=FakeLinear(issues=[issue(priority=0)]))
    out = json.loads(capsys.readouterr().out)
    assert out["ready"] is False and out["missing"] == ["Priority (the issue's priority field)"]


# ── Linear transport: a 429 is backed off, anything else fails closed ───────


class _Resp:
    def __init__(self, body):
        self.body, self.headers = body, {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *a):
        return self.body


def _http_error(code, retry_after=None):
    import email.message
    import urllib.error
    h = email.message.Message()
    if retry_after:
        h["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://x", code, "err", h, None)


def test_a_429_is_retried_after_backing_off(monkeypatch):
    calls, slept = [], []

    def urlopen(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise _http_error(429, "7")
        return _Resp(json.dumps({"data": {"viewer": {"id": "me"}}}).encode())
    monkeypatch.setattr(ir.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ir.time, "sleep", slept.append)
    assert ir.Linear("k").viewer_id() == "me"
    assert len(calls) == 3 and slept == [7, 7]


def test_persistent_429_and_other_errors_fail_closed(monkeypatch):
    import pytest
    monkeypatch.setattr(ir.time, "sleep", lambda s: None)
    for code in (429, 401):
        def urlopen(req, timeout, code=code):
            raise _http_error(code)
        monkeypatch.setattr(ir.urllib.request, "urlopen", urlopen)
        with pytest.raises(ir.LinearError, match=str(code)):
            ir.Linear("k").viewer_id()


def test_a_graphql_error_fails_closed(monkeypatch):
    import pytest
    monkeypatch.setattr(ir.urllib.request, "urlopen",
                        lambda req, timeout: _Resp(json.dumps({"errors": [{"message": "Entity not found"}]}).encode()))
    with pytest.raises(ir.LinearError, match="Entity not found"):
        ir.Linear("k").issue("EMA-0")


def test_a_missing_key_fails_closed():
    import pytest
    with pytest.raises(ir.LinearError, match="LINEAR_API_KEY"):
        ir.Linear(None)


def test_a_terse_real_section_counts_but_a_placeholder_word_does_not():
    assert ir.check(issue(BACKLOG_ITEM.replace("* Off-site copies.", "* S3."))).ready
    for word in ("TBD", "todo", "N/A", "..."):
        assert ir.check(issue(BACKLOG_ITEM.replace("* Off-site copies.", f"* {word}"))).missing == ["Out of scope"]


def test_the_old_scorer_comment_is_replaced_not_duplicated():
    # pipeline #278 (2026-10-06) posted 0-100 comments under the dropped scorer's marker on 5 issues
    lin = FakeLinear([{"id": "c5", "body": "**Issue readiness (weyland scorer)** — NOT READY · 75/100", "user": "me"}])
    assert ir.upsert_comment(lin, "u", f"{ir.MARKER} — READY") == "updated"
    assert lin.writes == [("update", "c5", f"{ir.MARKER} — READY")]


# ── an untouched template is NOT READY — the real Linear template bodies (fixtures/issue-readiness) ──

TEMPLATES = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "issue-readiness",
                                        "linear-templates.json")))["templates"]
LABELS = {"bug": ["Bug"], "spike": ["Spike"], "backlog item": [], "bucket": []}
TITLES = {"bucket": "B<n> — <area> (bucket)"}


def _from_template(kind):
    return ir.Issue("EMA-0", "u", TITLES.get(kind, "B<n> — "), TEMPLATES[kind], 0, LABELS[kind])


def test_every_untouched_template_is_not_ready_with_every_section_missing():
    for kind in ir.REQUIRED:
        r = ir.check(_from_template(kind))
        assert r.kind == kind
        assert r.missing == [n for n, _ in ir.REQUIRED[kind]] + [ir.PRIORITY_ITEM], (kind, r.missing)


def test_every_required_section_is_a_heading_its_template_has():
    # the code's standard and the templates must not drift apart: each required section names a template heading
    for kind, required in ir.REQUIRED.items():
        headings = [h for h in ir.parse_sections(TEMPLATES[kind]) if h != ir.PREAMBLE]
        for name, aliases in required:
            assert any(h.startswith(a) for h in headings for a in aliases), (kind, name)


def test_only_http_urls_are_ever_opened(monkeypatch):
    # ISSUE_READINESS_LINEAR_URL is an env override; a file:// or custom scheme must never reach urlopen (bandit B310)
    import pytest
    opened = []
    monkeypatch.setattr(ir.urllib.request, "urlopen", lambda req, timeout: opened.append(req))
    with pytest.raises(ir.LinearError, match="scheme"):
        ir._post_json("file:///etc/passwd", {}, {}, 5)
    assert not opened
