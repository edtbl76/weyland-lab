"""Tests for issue_readiness.py — the lab's own issue-readiness scorer (B190, replaces SpecBot).

SpecBot (a third-party cloud judge, 25 analyses/month) scored issues on 8 dimensions; its total is the plain mean of
the 8, rounded (EMA-240: 51 / 70 / 75, reproduced below). The lab's scorer keeps that shape and adds what SpecBot
could not give: deterministic section checks BEFORE any model call, a native-priority rule instead of a hidden
estimate penalty, and fail-closed behavior — a judge that is down or answers garbage is exit 2, never a score.

These pin the decisions. The LLM is a fake callable and Linear a fake object, so nothing leaves the process.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import readiness_judge as ir

FULL = """## Why

The nightly backup has no restore drill, so nobody knows whether it restores.

## Scope

Add a drill job and document it.

## Expected behavior

Every night the drill restores the newest backup and reports its row counts.

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


def issue(description=FULL, priority=2, labels=(), title="B999 — Restore drill", project="Weyland Lab", relations=1):
    return ir.Issue(identifier="EMA-999", uuid="u-999", title=title, description=description,
                    priority=priority, labels=list(labels), project=project, relations=relations)


EVIDENCE = "nobody knows whether it restores"      # a real quote from FULL


def answer(dims, score=90, confidence=85, evidence=EVIDENCE):
    return json.dumps({"scores": {d: {"score": score, "reason": f"{d} ok", "fix": f"improve {d}", "evidence": evidence}
                                  for d in dims}, "confidence": confidence})


class FakeLLM:
    """Records every prompt; returns the queued replies in order (a str, or an Exception to raise)."""

    def __init__(self, *replies, model="wl-judge-oss @ http://192.168.1.230:11434 (fallbacks 0)"):
        self.replies = list(replies)
        self.calls = []
        self.model = model

    def __call__(self, messages):
        self.calls.append(messages)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]   # the last reply repeats (votes)
        if isinstance(reply, Exception):
            raise reply
        return reply, self.model


def requested(llm, call=0):
    """The dimension keys the scorer asked the judge for, read back from the prompt it sent."""
    return set(json.loads(llm.calls[call][-1]["content"].split("DIMENSIONS_JSON:", 1)[1].split("\n", 1)[0]))


def judged(iss):
    """The dims a full LLM pass would be asked for, for building a matching fake answer."""
    return ir.plan(iss).judged


# ── sections + kinds ────────────────────────────────────────────────────────


def test_sections_are_keyed_by_lowercased_heading():
    s = ir.parse_sections(FULL)
    assert "acceptance criteria" in s and "edge cases & failure modes" in s
    assert "drill restores" in s["acceptance criteria"]


def test_bold_line_headings_count_as_sections():
    # EMA-240 and the backlog-style issues mark sections as bold lines, not `##` headings.
    s = ir.parse_sections("**Why.** It broke.\n\n**Acceptance criteria**\n- [ ] the drill prints row counts\n")
    assert "why" in s and "It broke." in s["why"]
    assert "drill prints" in s["acceptance criteria"]
    assert ir.has_section(s, "acceptance_criteria")


def test_bold_text_inside_a_sentence_is_not_a_heading():
    s = ir.parse_sections("## Why\n\nThis is **really** broken and **must** be fixed today.\n")
    assert list(s) == ["why"]


def test_kind_comes_from_labels_then_title():
    assert ir.issue_kind(issue(labels=["Bug"])) == "bug"
    assert ir.issue_kind(issue(labels=["Spike"])) == "spike"
    assert ir.issue_kind(issue(title="B78 — Data-mesh maturity (bucket)")) == "bucket"
    assert ir.issue_kind(issue()) == "feature"


# ── deterministic checks: no model call for what a rule can decide ──────────


def test_missing_acceptance_criteria_scores_at_most_20_without_asking_the_model():
    desc = FULL.split("## Acceptance criteria")[0] + "## Out of scope\n\n* Off-site copies.\n"
    iss = issue(desc.replace("## Edge cases", "## Ignored"))
    llm = FakeLLM(answer(judged(iss)))
    r = ir.score(iss, llm)
    assert r.scores["acceptance_criteria"].score <= 20
    assert r.scores["acceptance_criteria"].source == "rule"
    assert "acceptance_criteria" not in requested(llm)


def test_template_placeholder_counts_as_missing():
    desc = FULL.replace("- [ ] The drill restores the newest backup read-only and prints its row counts.",
                        "Testable, pass/fail — each one a check someone (or an agent) can run.\n\n- [ ] (criterion)")
    assert ir.plan(issue(desc)).fixed["acceptance_criteria"].score <= 20


def test_no_ac_section_at_all_still_scores_the_rest_with_the_model():
    iss = issue("## Why\n\nBecause.\n")
    llm = FakeLLM(answer(judged(iss), score=70))
    r = ir.score(iss, llm)
    assert len(llm.calls) == 1
    assert r.scores["acceptance_criteria"].score <= 20 and r.scores["edge_cases"].score <= 20


def test_reproduction_is_not_applicable_unless_it_is_a_bug():
    assert "reproduction" in ir.plan(issue()).na
    bug = issue(FULL.replace("## Why", "## Observed") + "\n## Repro\n\n1. run it\n", labels=["Bug"])
    assert "reproduction" not in ir.plan(bug).na


def test_bug_with_no_repro_section_is_fixed_low():
    assert ir.plan(issue(labels=["Bug"])).fixed["reproduction"].score <= 20


def test_no_priority_caps_priority_and_scope():
    iss = issue(priority=0)
    r = ir.score(iss, FakeLLM(answer(judged(iss), score=95)))
    assert r.scores["priority_scope"].score <= 30
    assert "priority" in r.scores["priority_scope"].reason.lower()


def test_a_missing_estimate_is_never_penalised():
    # The lab does not use estimates (owner's choice, 2026-09-26): nothing in the issue model even reads one.
    iss = issue()
    r = ir.score(iss, FakeLLM(answer(judged(iss), score=90)))
    assert r.scores["priority_scope"].score == 90


# ── total, status, blockers ─────────────────────────────────────────────────


@pytest.mark.parametrize("vector,total", [
    ([82, 84, 12, 10, 44, 82, 84, 12], 51),   # SpecBot EMA-240 run 1
    ([82, 84, 90, 82, 44, 82, 84, 12], 70),   # run 2
    ([82, 84, 90, 82, 84, 82, 84, 12], 75),   # run 4
])
def test_total_is_the_rounded_mean_like_specbot(vector, total):
    assert ir.total_of(vector) == total


def test_not_applicable_dimensions_are_left_out_of_the_mean():
    iss = issue()
    r = ir.score(iss, FakeLLM(answer(judged(iss), score=80)))
    assert "reproduction" not in r.scores
    assert r.total == 80 and r.status == "READY"


def test_missing_definition_of_done_is_a_blocker_not_a_suggestion():
    iss = issue("## Why\n\nBecause.\n\n## Out of scope\n\n* x\n")
    r = ir.score(iss, FakeLLM(answer(judged(iss), score=85)))
    assert any("acceptance criteria" in b.lower() for b in r.blockers)
    assert r.status == "NOT_READY"


def test_mid_scores_become_suggested_fixes():
    iss = issue()
    dims = judged(iss)
    reply = json.loads(answer(dims, score=90))
    reply["scores"]["dependencies"] = {"score": 55, "reason": "unclear", "fix": "Name what this waits on."}
    r = ir.score(iss, FakeLLM(json.dumps(reply)))
    assert "Name what this waits on." in r.fixes and not r.blockers


# ── the judge fails closed ──────────────────────────────────────────────────


def test_a_high_score_whose_quote_is_not_in_the_issue_is_capped():
    # A 7B judge scored nearly everything 95-100 (EMA-252: 97 vs SpecBot 62). Every score must cite the issue; a
    # quote the issue does not contain is the judge inventing support, and the code — not the model — catches it.
    iss = issue()
    r = ir.score(iss, FakeLLM(answer(judged(iss), score=95, evidence="the system auto-scales to zero")))
    assert r.scores["dependencies"].score <= 40
    assert "not found in the issue" in r.scores["dependencies"].reason


def test_quote_matching_ignores_case_whitespace_and_markdown():
    iss = issue()
    r = ir.score(iss, FakeLLM(answer(judged(iss), score=85, evidence="Nobody  knows **whether** it restores")))
    assert r.scores["dependencies"].score == 85


def test_a_near_verbatim_quote_with_list_markers_and_a_trim_still_counts():
    # Observed live (qwen2.5:7b, EMA-254): quotes keep `* ` / `[ ]` bullets, span two list items, or drop a clause.
    desc = "## Edge cases\n\n* An empty or truncated value is accepted silently by Kubernetes, so verify the length.\n"
    assert ir.quoted("* An empty or truncated value is accepted silently by Kubernetes → verify the length.", desc)
    assert not ir.quoted("The service scales to zero when idle and wakes on the first request.", desc)


def test_model_scores_are_capped_at_the_ceiling():
    iss = issue()
    r = ir.score(iss, FakeLLM(answer(judged(iss), score=100)))
    assert max(s.score for s in r.scores.values()) == ir.JUDGE_MAX


def test_no_dependency_statement_and_no_relation_is_fixed_low():
    p = ir.plan(issue(relations=0))
    assert p.fixed["dependencies"].score <= 20 and "dependencies" not in p.judged


def test_a_linear_relation_or_a_stated_none_counts_as_dependencies():
    assert "dependencies" in ir.plan(issue(relations=1)).judged
    assert "dependencies" in ir.plan(issue(FULL + "\n**Dependencies:** none.\n", relations=0)).judged
    assert "dependencies" in ir.plan(issue(FULL + "\nThis depends on B134 landing first.\n", relations=0)).judged


def test_no_expected_outcome_section_caps_expected_behavior():
    no_expected = FULL.split("## Expected behavior")[0] + "## Technical context" + FULL.split("## Technical context")[1]
    assert ir.plan(issue(no_expected)).caps["expected_behavior"][0] == 50
    assert "expected_behavior" not in ir.plan(issue()).caps


def test_a_low_score_needs_no_quote():
    iss = issue()
    r = ir.score(iss, FakeLLM(answer(judged(iss), score=30, evidence="")))
    assert r.scores["dependencies"].score == 30


def test_malformed_json_is_retried_once_then_succeeds():
    iss = issue()
    llm = FakeLLM("not json", answer(judged(iss)))
    assert ir.score(iss, llm).total == 90 and len(llm.calls) == 2


def test_two_malformed_replies_are_invalid_never_a_score():
    with pytest.raises(ir.ScorerInvalid):
        ir.score(issue(), FakeLLM("not json", "{}"))


def test_out_of_range_score_is_invalid():
    iss = issue()
    bad = answer(judged(iss), score=140)
    with pytest.raises(ir.ScorerInvalid):
        ir.score(iss, FakeLLM(bad, bad))


def test_a_missing_dimension_in_the_reply_is_invalid():
    iss = issue()
    short = answer(sorted(judged(iss))[1:])
    with pytest.raises(ir.ScorerInvalid):
        ir.score(iss, FakeLLM(short, short))


def test_unreachable_gateway_is_unavailable():
    with pytest.raises(ir.ScorerUnavailable):
        ir.score(issue(), FakeLLM(ir.ScorerUnavailable("connection refused"), ir.ScorerUnavailable("again")))


def test_long_description_is_truncated_visibly():
    iss = issue(FULL + "\n" + "x" * (ir.MAX_DESCRIPTION_CHARS + 500))
    llm = FakeLLM(answer(judged(iss)))
    r = ir.score(iss, llm)
    assert r.truncated
    assert len(llm.calls[0][-1]["content"]) < ir.MAX_DESCRIPTION_CHARS + 6000
    assert "truncated" in ir.render_comment(r).lower()


def test_bucket_is_skipped_not_scored():
    llm = FakeLLM()
    r = ir.score(issue(title="B78 — Data-mesh maturity (bucket)"), llm)
    assert r.skipped and not llm.calls


# ── the comment ─────────────────────────────────────────────────────────────


def test_comment_names_model_and_rubric_version():
    iss = issue()
    body = ir.render_comment(ir.score(iss, FakeLLM(answer(judged(iss)))))
    assert ir.MARKER in body and f"rubric v{ir.RUBRIC_VERSION}" in body
    assert "wl-judge-oss" in body and "90/100" in body


class FakeLinear:
    def __init__(self, comments=(), issues=()):
        self.comments = [dict(c) for c in comments]
        self.issues = list(issues)
        self.writes = []

    def open_high(self, project):
        return self.issues

    def issue(self, identifier):
        return self.issues[0]

    def viewer_id(self):
        return "me"

    def comments_on(self, issue_uuid):
        return self.comments

    def create_comment(self, issue_uuid, body):
        self.writes.append(("create", body))

    def update_comment(self, comment_id, body):
        self.writes.append(("update", comment_id, body))


def test_first_score_creates_one_comment():
    lin = FakeLinear()
    assert ir.upsert_comment(lin, "u-1", f"{ir.MARKER} x") == "created"
    assert lin.writes[0][0] == "create"


def test_rescoring_updates_the_same_comment():
    lin = FakeLinear([{"id": "c1", "body": f"{ir.MARKER} old", "user": "me"}])
    assert ir.upsert_comment(lin, "u-1", f"{ir.MARKER} new") == "updated"
    assert lin.writes == [("update", "c1", f"{ir.MARKER} new")]


def test_unchanged_score_writes_nothing():
    lin = FakeLinear([{"id": "c1", "body": f"{ir.MARKER} same", "user": "me"}])
    assert ir.upsert_comment(lin, "u-1", f"{ir.MARKER} same") == "unchanged"
    assert not lin.writes


def test_someone_elses_comment_with_the_marker_is_not_ours():
    lin = FakeLinear([{"id": "c9", "body": f"quoting {ir.MARKER}", "user": "someone"}])
    assert ir.upsert_comment(lin, "u-1", f"{ir.MARKER} x") == "created"


# ── CLI exit codes ──────────────────────────────────────────────────────────


def write_issue(tmp_path, iss):
    p = tmp_path / "issue.json"
    p.write_text(json.dumps(iss.__dict__))
    return str(p)


def test_cli_below_threshold_exits_1(tmp_path, capsys):
    iss = issue()
    rc = ir.main(["--issue-file", write_issue(tmp_path, iss), "--no-comment"], llm=FakeLLM(answer(judged(iss), 60)))
    assert rc == 1 and "NOT READY" in capsys.readouterr().out


def test_cli_ready_exits_0(tmp_path, capsys):
    iss = issue()
    rc = ir.main(["--issue-file", write_issue(tmp_path, iss), "--no-comment"], llm=FakeLLM(answer(judged(iss), 90)))
    out = capsys.readouterr().out
    assert rc == 0 and "READY" in out and "90/100" in out


def test_cli_unavailable_exits_2_with_reason(tmp_path, capsys):
    rc = ir.main(["--issue-file", write_issue(tmp_path, issue()), "--no-comment"],
                 llm=FakeLLM(ir.ScorerUnavailable("refused"), ir.ScorerUnavailable("refused")))
    assert rc == 2 and "scorer unavailable" in capsys.readouterr().err


def test_cli_invalid_judge_exits_2_with_reason(tmp_path, capsys):
    rc = ir.main(["--issue-file", write_issue(tmp_path, issue()), "--no-comment"], llm=FakeLLM("x", "y"))
    assert rc == 2 and "scorer invalid" in capsys.readouterr().err


def test_cli_with_no_issue_is_a_usage_error(capsys):
    assert ir.main([], llm=FakeLLM()) == 2


def test_cli_json_output_is_machine_readable(tmp_path, capsys):
    iss = issue()
    ir.main(["--issue-file", write_issue(tmp_path, iss), "--no-comment", "--json"], llm=FakeLLM(answer(judged(iss))))
    out = json.loads(capsys.readouterr().out)
    assert out["total"] == 90 and out["scores"]["acceptance_criteria"]["score"] == 90


# ── content digest: the sweep re-scores only what changed ───────────────────


def test_digest_is_stable_and_tracks_every_scored_input():
    base = ir.digest(issue())
    assert base == ir.digest(issue())
    for changed in (issue(FULL + "x"), issue(priority=3), issue(labels=["Bug"]), issue(relations=0),
                    issue(title="B999 — renamed")):
        assert ir.digest(changed) != base


def test_comment_carries_the_digest():
    iss = issue()
    r = ir.score(iss, FakeLLM(answer(judged(iss))))
    assert f"digest {ir.digest(iss)}" in ir.render_comment(r)








def test_the_default_judge_is_the_16k_gpt_oss_alias():
    assert ir.DEFAULT_MODEL == "wl-judge-oss"


# ── which model answered (LiteLLM echoes the alias; the backend is in headers — observed live, LiteLLM 1.93.0) ──


def test_answered_by_names_backend_and_fallbacks_behind_litellm():
    h = {"x-litellm-model-api-base": "http://192.168.1.230:11434", "x-litellm-attempted-fallbacks": "1"}
    assert ir.answered_by({"model": "wl-judge-oss"}, h, "wl-judge-oss") == \
        "wl-judge-oss @ http://192.168.1.230:11434 (fallbacks 1)"


def test_answered_by_is_just_the_model_when_not_behind_litellm():
    assert ir.answered_by({"model": "gpt-oss:20b-judge"}, {}, "x") == "gpt-oss:20b-judge"
    assert ir.answered_by({}, {}, "wl-judge-oss") == "wl-judge-oss"


# ── found on the EMA-240 pre-fix reconstruction (2026-10-06) ────────────────


def test_an_opening_paragraph_before_any_heading_is_the_problem_statement():
    # EMA-240 / EMA-243 open with the problem and only then start headings — that is an objective, not a missing one.
    desc = "The lab has no time tracking, so nobody knows where the hours go.\n\n## Scope\n\n1. Install it.\n"
    assert "objective" not in ir.plan(issue(desc)).caps


def test_a_capped_dimension_gives_the_rules_fix_not_the_models():
    desc = FULL.split("## Technical context")[0] + "## Acceptance criteria" + FULL.split("## Acceptance criteria")[1]
    iss = issue(desc)
    reply = json.loads(answer(judged(iss), score=90))
    reply["scores"]["technical_context"]["fix"] = "None needed; context is complete."
    r = ir.score(iss, FakeLLM(json.dumps(reply)))
    assert r.scores["technical_context"].score == 50
    assert "None needed" not in r.scores["technical_context"].fix
    assert "Technical context" in r.scores["technical_context"].fix


def test_no_fallbacks_switch_reaches_the_gateway(monkeypatch):
    # The judge eval's second judge must be THAT model: a LiteLLM fallback would silently swap in another one
    # (wl-default's chain ends in a paid model). ISSUE_READINESS_NO_FALLBACKS=1 sends LiteLLM's disable_fallbacks.
    sent = {}

    def fake_post(url, payload, headers, timeout, error, with_headers=False):
        sent.update(payload)
        return {"choices": [{"message": {"content": "{}"}}], "model": "wl-default"}, {}
    monkeypatch.setattr(ir, "_post_json", fake_post)
    ir.litellm_client({"LITELLM_API_KEY": "k", "ISSUE_READINESS_NO_FALLBACKS": "1"})([])
    assert sent["disable_fallbacks"] is True
    sent.clear()
    ir.litellm_client({"LITELLM_API_KEY": "k"})([])
    assert "disable_fallbacks" not in sent


# ── votes: three judgements, the median per dimension (EMA-257 scored 83/83/79 on repeat — a verdict flip) ──


def test_the_median_of_three_votes_is_taken_per_dimension():
    iss = issue()
    dims = judged(iss)
    llm = FakeLLM(answer(dims, 70), answer(dims, 90), answer(dims, 80))
    r = ir.score(iss, llm, votes=3)
    assert len(llm.calls) == 3
    assert all(s.score == 80 for d, s in r.scores.items() if s.source == "llm")


def test_one_outlier_vote_cannot_move_the_verdict():
    iss = issue()
    dims = judged(iss)
    r = ir.score(iss, FakeLLM(answer(dims, 82), answer(dims, 40), answer(dims, 82)), votes=3)
    assert r.status == "READY"


def test_a_vote_that_fails_after_its_retry_fails_the_whole_score():
    iss = issue()
    dims = judged(iss)
    with pytest.raises(ir.ScorerInvalid):
        ir.score(iss, FakeLLM(answer(dims), "bad", "bad"), votes=3)


def test_the_default_is_three_votes():
    assert ir.DEFAULT_VOTES == 3


# ── rate limits: back off, never a partial score (B190 edge case; gemini-flash 429'd the judge eval, 2026-10-06) ──


class _Resp:
    def __init__(self, body):
        self.body, self.headers = body, {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, *a):
        return self.body


def _http_429(retry_after=None):
    import email.message
    import urllib.error
    h = email.message.Message()
    if retry_after:
        h["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://x", 429, "Too Many Requests", h, None)


def test_a_429_is_retried_after_backing_off(monkeypatch):
    calls, slept = [], []
    body = json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()

    def urlopen(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise _http_429("7")
        return _Resp(body)
    monkeypatch.setattr(ir.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ir.time, "sleep", slept.append)
    ir._post_json("http://x", {}, {}, 5, ir.ScorerUnavailable)
    assert len(calls) == 3 and slept == [7, 7]


def test_persistent_429_is_unavailable_not_a_score(monkeypatch):
    def urlopen(req, timeout):
        raise _http_429()
    monkeypatch.setattr(ir.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ir.time, "sleep", lambda s: None)
    with pytest.raises(ir.ScorerUnavailable, match="429"):
        ir._post_json("http://x", {}, {}, 5, ir.ScorerUnavailable)


def test_other_http_errors_are_not_retried(monkeypatch):
    import email.message
    import urllib.error
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError("http://x", 401, "Unauthorized", email.message.Message(), None)
    monkeypatch.setattr(ir.urllib.request, "urlopen", urlopen)
    with pytest.raises(ir.ScorerUnavailable, match="401"):
        ir._post_json("http://x", {}, {}, 5, ir.ScorerUnavailable)
    assert len(calls) == 1


def test_the_retry_tells_the_judge_what_was_wrong():
    # At temperature 0 an identical retry tends to repeat the identical bad reply (a damaged EMA-258 failed twice,
    # 2026-10-06). The retry carries the bad reply and the reason, so the second prompt differs.
    iss = issue()
    llm = FakeLLM("{}", answer(judged(iss)))
    ir.score(iss, llm)
    retry = llm.calls[1]
    assert retry[-2] == {"role": "assistant", "content": "{}"}
    assert retry[-1]["role"] == "user" and "unusable" in retry[-1]["content"]
    assert len(llm.calls[0]) == 2                       # the first attempt is the plain prompt


# ── adaptive votes: one judgement, three only near the threshold (2026-10-06: three votes on every issue made the
# first CI sweep ~10 min/issue on a GPU the 20b model does not fit; the widest repeat spread measured was 4) ──


def test_a_score_far_from_the_threshold_takes_one_judgement():
    iss = issue()
    llm = FakeLLM(answer(judged(iss), 50))
    r = ir.score(iss, llm, votes=3, adaptive=True)
    assert len(llm.calls) == 1 and r.total == 50


def test_a_borderline_score_takes_three_and_uses_the_median():
    iss = issue()
    dims = judged(iss)
    llm = FakeLLM(answer(dims, 78), answer(dims, 84), answer(dims, 82))
    r = ir.score(iss, llm, votes=3, adaptive=True)
    assert len(llm.calls) == 3
    assert all(s.score == 82 for s in r.scores.values() if s.source == "llm")


def test_the_borderline_band_covers_the_measured_spread():
    assert ir.BORDERLINE >= 4


# ── the context guard: a reply that filled the window is invalid, never a score ──


def test_a_reply_that_exhausted_the_context_window_is_invalid(monkeypatch):
    def fake_post(url, payload, headers, timeout, error, with_headers=False):
        return {"choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": ir.JUDGE_CONTEXT - 10, "completion_tokens": 10}}, {}
    monkeypatch.setattr(ir, "_post_json", fake_post)
    with pytest.raises(ir.ScorerInvalid, match="context"):
        ir.litellm_client({"LITELLM_API_KEY": "k"})([])


def test_the_description_cap_fits_the_window():
    # measured on gpt-oss:20b, 2026-10-06: prompt ~= 1450 + chars/3.6 tokens; replies ~450-500 tokens
    assert 1450 + ir.MAX_DESCRIPTION_CHARS / 3.6 + 1000 < ir.JUDGE_CONTEXT


# ── the sweep's time budget: what it could not reach is deferred, never passed ──


def test_the_sweep_defers_issues_past_its_budget(monkeypatch, capsys):
    a, b = issue(), issue(title="B998 — second")
    b.identifier, b.uuid = "EMA-998", "u-998"
    clock = iter([0, 0, 10_000, 10_000, 10_000])
    monkeypatch.setattr(ir.time, "monotonic", lambda: next(clock))
    rc = ir.main(["--sweep", "--no-comment", "--budget", "60"], llm=FakeLLM(answer(judged(a), 90)),
                 linear=FakeLinear(issues=[a, b]))
    out = capsys.readouterr().out
    assert "EMA-999" in out and "EMA-998  deferred" in out
    assert rc == 1                                        # deferred is not a pass



def test_the_research_harness_never_comments(capsys):
    # B190 dropped this scorer (2026-10-06); the production check is issue_readiness.py — this one must not write
    assert ir.main(["EMA-999"], llm=FakeLLM(), linear=FakeLinear()) == 2
    assert "research harness" in capsys.readouterr().err


def test_only_http_urls_are_ever_opened(monkeypatch):
    opened = []
    monkeypatch.setattr(ir.urllib.request, "urlopen", lambda req, timeout: opened.append(req))
    with pytest.raises(ir.ScorerUnavailable, match="scheme"):
        ir._post_json("file:///etc/passwd", {}, {}, 5, ir.ScorerUnavailable)
    assert not opened
