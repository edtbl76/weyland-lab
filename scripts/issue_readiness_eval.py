#!/usr/bin/env python3
"""Judge eval for the B190 issue-readiness scorer — proves the judge measures QUALITY inside a section, not just presence.

The scorer's rules (no acceptance criteria -> 10, no priority -> cap 30, ...) are deterministic and unit-tested. What no
rule can check is whether a section that EXISTS is any good. Three runs prove that part, and are re-run whenever the
judge model, its alias or the rubric changes (docs/runbooks/issue-readiness.md § Proving the judge):

  defects     Controlled damage. Each real issue is degraded in ONE section the way a weak author writes it (concrete
              criteria -> "it works as expected", the context table -> "the relevant parts will change"). A case passes
              when the judge cuts THAT dimension by >= 20 points to <= 60; collateral movement on the other dimensions is
              reported, so a judge that just marks everything down is visible.
  agreement   A second, stronger judge scores the same issues; per-dimension agreement shows whether the scores are a
              property of the issue or an artifact of one small model.
  stability   The same issue scored N times: spread and READY/NOT READY flips at temperature 0.

Scores here are the JUDGE's (after the quote check), with the rules switched off — the eval measures the model, the
rules are measured by their own tests.

  issue_readiness_eval.py snapshot EMA-257 EMA-254 ...        save issues to eval/issue-readiness/issues/
  issue_readiness_eval.py defects eval/issue-readiness/issues/*.json
  issue_readiness_eval.py agreement --model-b wl-default eval/issue-readiness/issues/*.json
"""
import argparse
import json
import os
import re
import sys
from collections import namedtuple

import issue_readiness as ir

DROP_REQUIRED = 20           # the damaged dimension must fall at least this far ...
DAMAGED_MAX = 60             # ... and land at or below this — "acceptable" after damage means the judge missed it
BASE_MIN = 70                # a case counts only if the judge rated the section good BEFORE the damage

# An operator removes ONE property from the whole issue, the way a weak author leaves it out: every section group in
# `sections` must exist and has its body replaced; `scrub` also strips system names from every other section. Removing a
# property from one heading while the issue still states it elsewhere tests nothing — EMA-254 names its namespace,
# files and paths in Scope, so deleting only its Technical context table rightly left the judge at 90 (2026-10-06).
Operator = namedtuple("Operator", "dimension sections scrub")
AC = ("acceptance criteria", "exit criteria")
OPERATORS = {
    "vague_acceptance": Operator("acceptance_criteria", (
        (AC, "- [ ] It works as expected.\n- [ ] Tests pass.\n- [ ] Docs are updated.\n"),), False),
    "generic_edge_cases": Operator("edge_cases", (
        (("edge cases",), "* Things could go wrong.\n* Errors should be handled gracefully.\n"),), False),
    "contextless_technical": Operator("technical_context", (
        (("technical context",), "The relevant parts of the system will be changed as needed.\n"),), True),
    "solution_only_why": Operator("objective", (
        (("why", "purpose", "problem", ir.PREAMBLE), "We will build this.\n"),), False),
    "boundless_scope": Operator("priority_scope", ((("out of scope",), "* Nothing in particular.\n"),), False),
    # the end state lives in Scope AND in the acceptance criteria on the lab's template — remove it from both
    "no_end_state": Operator("expected_behavior", (
        (("scope", "goal", "expected", "outcome", "deliverable", "candidates"), "1. Investigate.\n2. Implement.\n"
                                                                                 "3. Document.\n"),
        (AC, "- [ ] The code is written.\n- [ ] The PR is merged.\n")), False),
}
SYSTEM_NAME = re.compile(r"`[^`\n]*`|https?://\S+|\b[\w.-]+(?:/[\w.-]+)+\b|\b(?:mother|rogueone|weyland)\b", re.I)


# ── damage ──────────────────────────────────────────────────────────────────


def _heading(line):
    """(heading text, the line to keep) for a heading line, else None. A bold heading keeps only its bold run."""
    m = ir.HEADING.match(line)
    if m:
        return m.group("h").strip().rstrip(".:").lower(), line
    m = ir.BOLD_HEADING.match(line)
    if m:
        return m.group("h").strip().rstrip(".:").lower(), f"**{m.group('h')}**"
    return None


def _replace(markdown, aliases, body):
    """(markdown with every section matching `aliases` given `body`, whether any matched)."""
    has_preamble = ir.PREAMBLE in aliases and bool(ir.parse_sections(markdown).get(ir.PREAMBLE, "").strip())
    out, hit, skipping = ([body] if has_preamble else []), has_preamble, has_preamble
    for line in markdown.splitlines():
        h = _heading(line)
        if h:
            skipping = any(h[0].startswith(a) for a in aliases if a != ir.PREAMBLE)
            out.append(h[1] if skipping else line)
            if skipping:
                out.append(body)
                hit = True
        elif not skipping:
            out.append(line)
    return "\n".join(out) + "\n", hit


def damage(markdown, op_name):
    """The issue with the operator's property removed; None if the issue lacks a section the operator needs."""
    op = OPERATORS[op_name]
    for aliases, body in op.sections:
        markdown, hit = _replace(markdown, aliases, body)
        if not hit:
            return None
    if op.scrub:
        markdown = SYSTEM_NAME.sub("the relevant component", markdown)
    return markdown


# ── scoring with the rules off ──────────────────────────────────────────────


def judgeable(issue):
    """Every dimension the judge can score for this issue (reproduction only on a bug)."""
    return [d for d, _ in ir.DIMENSIONS if d not in ir.plan(issue).na]


def judged_scores(issue, llm):
    dims = judgeable(issue)
    messages, _ = ir.build_messages(issue, dims)
    scores, _, _ = ir.judge(llm, messages, dims)
    return {d: ir._supported(s, issue.description).score for d, s in scores.items()}


# ── metrics ─────────────────────────────────────────────────────────────────


def judge_case(base, damaged, dim):
    drop = base[dim] - damaged[dim]
    others = [abs(base[d] - damaged[d]) for d in base if d != dim and d in damaged]
    return {"drop": drop, "after": damaged[dim], "collateral": max(others, default=0),
            "passed": drop >= DROP_REQUIRED and damaged[dim] <= DAMAGED_MAX}


def agreement(a, b, tolerance=15):
    per_dim, pairs, within = {}, 0, 0
    for key in a.keys() & b.keys():
        for dim in a[key].keys() & b[key].keys():
            gap = abs(a[key][dim] - b[key][dim])
            pairs += 1
            within += gap <= tolerance
            d = per_dim.setdefault(dim, {"gaps": []})
            d["gaps"].append(gap)
    for d in per_dim.values():
        d["max_gap"], d["mean_gap"] = max(d["gaps"]), round(sum(d["gaps"]) / len(d["gaps"]), 1)
        del d["gaps"]
    return {"pairs": pairs, "within": within, "tolerance": tolerance, "per_dimension": per_dim}


def stability(runs):
    """{issue: [(total, status), ...]} -> {issue: {spread, flips}}."""
    return {k: {"spread": max(t for t, _ in v) - min(t for t, _ in v), "flips": len({s for _, s in v}) > 1}
            for k, v in runs.items()}


# ── CLI ─────────────────────────────────────────────────────────────────────


def _load(paths):
    issues = []
    for p in paths:
        with open(p) as f:
            issues.append(ir.Issue(**json.load(f)))
    return issues


def run_defects(issues, llm, out=None):
    out = out or sys.stdout
    cases = []
    for iss in issues:
        base = judged_scores(iss, llm)
        for name, op in OPERATORS.items():
            text = damage(iss.description, name)
            if text is None or base.get(op.dimension, 0) < BASE_MIN:
                continue
            damaged = ir.Issue(**{**iss.__dict__, "description": text})
            c = {"issue": iss.identifier, "operator": name, "dimension": op.dimension, "base": base[op.dimension]}
            try:
                c.update(judge_case(base, judged_scores(damaged, llm), op.dimension), invalid=False)
            except ir.ScorerInvalid as e:              # recorded as a miss, never skipped and never an abort
                c.update(drop=None, after=None, collateral=None, passed=False, invalid=True, error=str(e))
            cases.append(c)
            print(json.dumps(c), file=out, flush=True)
    passed = sum(c["passed"] for c in cases)
    print(json.dumps({"summary": "defects", "cases": len(cases), "passed": passed}), file=out)
    return cases


def run_agreement(issues, llm_a, llm_b, out=None):
    out = out or sys.stdout
    a = {i.identifier: judged_scores(i, llm_a) for i in issues}
    b = {i.identifier: judged_scores(i, llm_b) for i in issues}
    for key in sorted(a):
        print(json.dumps({"issue": key, "a": a[key], "b": b.get(key)}), file=out, flush=True)
    rep = agreement(a, b)
    print(json.dumps({"summary": "agreement", **rep}), file=out)
    return rep


def snapshot(identifiers, directory, linear):
    os.makedirs(directory, exist_ok=True)
    for ident in identifiers:
        iss = linear.issue(ident)
        with open(os.path.join(directory, f"{ident}.json"), "w") as f:
            json.dump(iss.__dict__, f, indent=1)
            f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="issue-readiness-eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("ids", nargs="+")
    s.add_argument("--dir", default="eval/issue-readiness/issues")
    d = sub.add_parser("defects")
    d.add_argument("files", nargs="+")
    g = sub.add_parser("agreement")
    g.add_argument("files", nargs="+")
    g.add_argument("--model-b", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "snapshot":
        snapshot(args.ids, args.dir, ir.Linear(os.environ.get("LINEAR_API_KEY")))
        return 0
    llm = ir.litellm_client(os.environ)
    if args.cmd == "defects":
        cases = run_defects(_load(args.files), llm)
        return 0 if cases and all(c["passed"] for c in cases) else 1
    env_b = {**os.environ, "ISSUE_READINESS_MODEL": args.model_b, "ISSUE_READINESS_NO_FALLBACKS": "1"}
    env_b.pop("LITELLM_API_BASE_B", None)
    if os.environ.get("LITELLM_API_BASE_B"):
        env_b["LITELLM_API_BASE"] = os.environ["LITELLM_API_BASE_B"]
    run_agreement(_load(args.files), llm, ir.litellm_client(env_b))
    return 0


if __name__ == "__main__":
    sys.exit(main())
