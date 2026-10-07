"""Tests for issue_readiness_eval.py — the evidence that B190's judge measures issue QUALITY, not just section presence.

The scorer's rules are deterministic and pinned in test_issue_readiness.py. What a rule cannot check is quality inside a
section that exists. This eval proves that part by controlled damage: take a real issue, degrade exactly one section the
way a weak author would (concrete criteria -> "it works as expected"), and require the judge to cut THAT dimension hard
while leaving the others near where they were. These pin the damage operators and the pass/fail arithmetic; the judge
itself is a fake here and is exercised live by the eval run.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import readiness_judge as ir
import issue_readiness_eval as ev

DOC = """The backup has never been restored, so nobody knows it works.

## Why

Restores are untested.

## Scope

Add a drill.

## Technical context

| Where | What | Role |
| -- | -- | -- |
| mother | k8s/foo/backup.yaml | changed |

## Acceptance criteria

- [ ] The drill restores the newest backup read-only and prints row counts.

## Edge cases & failure modes

* An empty backup directory exits 2.

## Out of scope

* Off-site copies.
"""

BOLD = "**Why.** Restores are untested.\n\n**Acceptance criteria**\n- [ ] the drill prints row counts\n\n**Out of scope**\n* x\n"


def test_damage_replaces_only_the_target_section_body():
    out = ev.damage(DOC, "vague_acceptance")
    assert "It works as expected." in out
    assert "prints row counts" not in out
    assert "An empty backup directory exits 2." in out and "k8s/foo/backup.yaml" in out
    assert "## Acceptance criteria" in out


def test_damage_handles_bold_pseudo_headings():
    out = ev.damage(BOLD, "vague_acceptance")
    assert "**Acceptance criteria**" in out and "It works as expected." in out
    assert "prints row counts" not in out and "Restores are untested." in out


def test_damage_of_the_problem_statement_covers_the_opening_paragraph_too():
    out = ev.damage(DOC, "solution_only_why")
    assert "nobody knows it works" not in out and "Restores are untested." not in out
    assert "We will build this." in out


def test_damage_returns_none_when_the_issue_has_no_such_section():
    assert ev.damage("## Why\n\nBecause.\n", "contextless_technical") is None


def test_every_operator_targets_a_scored_dimension():
    dims = {d for d, _ in ir.DIMENSIONS}
    assert all(op.dimension in dims for op in ev.OPERATORS.values())


def test_a_case_passes_on_a_big_targeted_drop():
    case = ev.judge_case({"acceptance_criteria": 90, "edge_cases": 80}, {"acceptance_criteria": 40, "edge_cases": 78},
                         "acceptance_criteria")
    assert case["drop"] == 50 and case["collateral"] == 2 and case["passed"]


def test_a_small_drop_fails():
    assert not ev.judge_case({"acceptance_criteria": 90}, {"acceptance_criteria": 75}, "acceptance_criteria")["passed"]


def test_a_drop_that_still_leaves_a_high_score_fails():
    # 95 -> 70 is a 25-point cut, but 70 still reads as acceptable — the judge did not see the damage for what it is.
    assert not ev.judge_case({"acceptance_criteria": 95}, {"acceptance_criteria": 70}, "acceptance_criteria")["passed"]


def test_agreement_counts_dimensions_within_tolerance():
    a = {"EMA-1": {"objective": 80, "edge_cases": 50}, "EMA-2": {"objective": 90, "edge_cases": 90}}
    b = {"EMA-1": {"objective": 70, "edge_cases": 85}, "EMA-2": {"objective": 85, "edge_cases": 88}}
    rep = ev.agreement(a, b, tolerance=15)
    assert rep["pairs"] == 4 and rep["within"] == 3
    assert rep["per_dimension"]["edge_cases"]["max_gap"] == 35


def test_stability_reports_spread_and_verdict_flips():
    runs = {"EMA-1": [(78, "NOT_READY"), (82, "READY"), (79, "NOT_READY")], "EMA-2": [(50, "NOT_READY")] * 3}
    rep = ev.stability(runs)
    assert rep["EMA-1"] == {"spread": 4, "flips": True} and rep["EMA-2"] == {"spread": 0, "flips": False}


def test_judged_scores_skip_rules_but_keep_the_evidence_check():
    iss = ir.Issue("EMA-9", "u", "B9 — x", DOC, 2, [], "Weyland Lab", 1)
    dims = ev.judgeable(iss)

    def llm(messages):
        reply = {d: {"score": 90, "evidence": "invented words that are not in the issue at all", "reason": "",
                     "fix": ""} for d in dims}
        return json.dumps({"scores": reply}), "fake"
    scores = ev.judged_scores(iss, llm)
    assert set(scores) == set(dims) and all(v == ir.UNSUPPORTED_CAP for v in scores.values())


# ── the runners, end to end with a fake judge ───────────────────────────────


class ScriptedJudge:
    """Scores every judged dimension `high`, except the damaged dimension of a damaged issue, which gets `low`.
    Quotes a line the (possibly damaged) issue still contains, so the evidence check passes."""

    def __init__(self, high=85, low=30):
        self.high, self.low = high, low

    def __call__(self, messages):
        user = messages[1]["content"]                       # the issue prompt (a retry appends a correction after it)
        dims = json.loads(user.split("DIMENSIONS_JSON:", 1)[1].split("\n", 1)[0])
        weak = {op.dimension for op in ev.OPERATORS.values() if op.sections[0][1].strip() in user}
        description = user.split("Description:\n", 1)[1]
        quote = next((ln for ln in description.splitlines() if len(ln.split()) >= 4), "")   # text it still has
        return json.dumps({"scores": {d: {"score": self.low if d in weak else self.high,
                                          "evidence": quote, "reason": "", "fix": ""}
                                      for d in dims}}), "fake"


def _snapshot(tmp_path, ident="EMA-1"):
    p = tmp_path / f"{ident}.json"
    p.write_text(json.dumps({"identifier": ident, "uuid": "u", "title": "B1 — x", "description": DOC, "priority": 2,
                             "labels": [], "project": "Weyland Lab", "relations": 1}))
    return str(p)


def test_run_defects_passes_a_judge_that_sees_the_damage(tmp_path, capsys):
    cases = ev.run_defects(ev._load([_snapshot(tmp_path)]), ScriptedJudge())
    assert cases and all(c["passed"] for c in cases)
    assert {c["operator"] for c in cases} >= {"vague_acceptance", "contextless_technical", "generic_edge_cases"}
    assert '"summary": "defects"' in capsys.readouterr().out


def test_run_defects_fails_a_lenient_judge(tmp_path):
    cases = ev.run_defects(ev._load([_snapshot(tmp_path)]), ScriptedJudge(high=85, low=85))
    assert cases and not any(c["passed"] for c in cases)


def test_run_agreement_compares_two_judges(tmp_path, capsys):
    files = ev._load([_snapshot(tmp_path, "EMA-1"), _snapshot(tmp_path, "EMA-2")])
    rep = ev.run_agreement(files, ScriptedJudge(high=80), ScriptedJudge(high=90))
    assert rep["pairs"] > 0 and rep["within"] == rep["pairs"]


SNAPSHOT_ISSUE = ir.Issue("EMA-0", "u", "t", "d", 2, [], "Weyland Lab", 0)


def test_snapshot_writes_one_file_per_issue(tmp_path):
    import dataclasses

    class Lin:
        def issue(self, ident):
            return dataclasses.replace(SNAPSHOT_ISSUE, identifier=ident)
    ev.snapshot(["EMA-1", "EMA-2"], str(tmp_path), Lin())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["EMA-1.json", "EMA-2.json"]
    assert ev._load([str(tmp_path / "EMA-1.json")])[0].identifier == "EMA-1"


def test_a_section_the_judge_already_scored_weak_is_not_a_case(tmp_path):
    # Damage can only be detected in a section that was good to begin with; a base of 40 has no room for a 20-point
    # drop, and counting it would make the judge look blind (or sharp) for reasons that have nothing to do with damage.
    cases = ev.run_defects(ev._load([_snapshot(tmp_path)]), ScriptedJudge(high=ev.BASE_MIN - 1, low=10))
    assert cases == []


# ── operators that remove the property everywhere, not just from one heading (found 2026-10-06: EMA-254 names its
# namespace, files and paths in Scope, so deleting only the Technical context table left the context intact and the
# judge was RIGHT to keep scoring 90) ──


def test_contextless_technical_strips_systems_from_every_section():
    doc = DOC.replace("Add a drill.", "Add a drill in `k8s/foo/drill.yaml` on mother.")
    out = ev.damage(doc, "contextless_technical")
    assert "k8s/foo" not in out and "`" not in out
    assert "The relevant parts of the system will be changed as needed." in out


def test_no_end_state_removes_the_outcome_from_scope_and_criteria():
    out = ev.damage(DOC, "no_end_state")
    assert "Add a drill." not in out and "prints row counts" not in out
    assert "- [ ] The code is written." in out and "1. Investigate." in out
    assert "An empty backup directory exits 2." in out


def test_operators_that_need_a_section_still_require_it():
    assert ev.damage("## Why\n\nBecause it broke.\n", "no_end_state") is None


def test_an_unusable_judgement_is_a_failed_case_not_an_abort(tmp_path, capsys):
    # 2026-10-06: one invalid reply (after its retry) aborted a 45-minute eval run on its 40th case.
    calls = []

    def judge(messages):
        calls.append(1)
        if "It works as expected." in messages[1]["content"]:
            return "not json", "fake"
        return ScriptedJudge()(messages)
    cases = ev.run_defects(ev._load([_snapshot(tmp_path)]), judge)
    bad = [c for c in cases if c["operator"] == "vague_acceptance"]
    assert bad and bad[0]["invalid"] and not bad[0]["passed"]
    assert len(cases) > 1                                   # the run went on to the other operators


# ── outcomes: does the score predict whether an agent's PR was merged? (arXiv 2512.21426 replication data) ──


def test_auc_is_the_probability_a_merged_issue_outscores_an_unmerged_one():
    assert ev.auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0
    assert ev.auc([0.1, 0.2, 0.8, 0.9], [1, 1, 0, 0]) == 0.0
    assert ev.auc([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]) == 0.5      # ties count half


def test_auc_needs_both_outcomes():
    import pytest
    with pytest.raises(ValueError):
        ev.auc([0.1, 0.2], [1, 1])


def test_bootstrap_interval_brackets_the_point_estimate():
    scores = [i / 100 for i in range(100)]
    labels = [1 if i > 40 else 0 for i in range(100)]
    lo, hi = ev.auc_interval(scores, labels, rounds=200, seed=1)
    assert lo <= ev.auc(scores, labels) <= hi and hi - lo < 0.2


def _paper_rows():
    def row(issue, pr, merged, agent="Copilot", state="closed", body="body text here"):
        return {"issue_id": issue, "pr_id": pr, "agent": agent, "state_pr": state, "merged": merged,
                "title_issue": f"t{issue}", "body_issue": body, "repo_key": "o/r", "number_issue": issue}
    return [row("1", "a", "True"), row("2", "b", "False"), row("3", "c", "True"), row("3", "d", "False"),
            row("4", "e", "True", agent=""), row("5", "f", "False", state="open"), row("6", "g", "True"),
            row("7", "h", "False"), row("8", "i", "False")]


def test_population_is_closed_copilot_prs_one_per_issue_without_conflicting_outcomes():
    pop = ev.outcome_population(_paper_rows())
    assert sorted(p["issue_id"] for p in pop) == ["1", "2", "6", "7", "8"]   # 3 conflicts, 4 not Copilot, 5 open


def test_sample_is_stratified_and_reproducible():
    pop = ev.outcome_population(_paper_rows())
    a = ev.stratified_sample(pop, per_class=2, seed=190)
    assert a == ev.stratified_sample(pop, per_class=2, seed=190)
    assert sorted(r["merged"] for r in a) == ["False", "False", "True", "True"]


def test_run_outcomes_scores_once_per_issue_resumes_and_summarizes(tmp_path):
    import csv as _csv
    data = tmp_path / "data.csv"
    rows = _paper_rows()
    for r in rows:
        r["body_issue"] = DOC if r["merged"] == "True" else "fix it"
    with open(data, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    calls = []

    def judge(messages):
        calls.append(1)
        return ScriptedJudge(high=80)(messages)
    out = str(tmp_path / "out.jsonl")
    ev.run_outcomes(str(data), out, judge, per_class=2, seed=190)
    assert len(calls) == 4                                    # one judgement per sampled issue
    ev.run_outcomes(str(data), out, judge, per_class=2, seed=190)
    assert len(calls) == 4                                    # resumed: nothing re-scored
    rep = ev.summarize_outcomes(out)
    assert rep["scored"] == 4 and rep["errors"] == 0
    assert "our judge, rules off (mean)" in rep["auc"] and "our product total" in rep["auc"]
