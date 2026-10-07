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
import csv
import json
import random
import os
import re
import sys
from collections import namedtuple

import readiness_judge as ir

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


# ── outcomes: does the score predict whether an agent's PR got merged? ──────
# Data: the replication package of "What Makes a GitHub Issue Ready for Copilot?" (arXiv 2512.21426,
# https://github.com/DaREf-MS/pr_prediction_from_issues) — GitHub issues handed to Copilot, each with whether the PR it
# produced was merged, plus the paper's own 32-criterion LLM rubric scores. The only issue-readiness ground truth found
# (2026-10-06); SpecBot publishes no accuracy data at all.


def auc(scores, labels):
    """P(a merged issue scores above an unmerged one); ties count half (Mann-Whitney)."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        raise ValueError("AUC needs both outcomes")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def auc_interval(scores, labels, rounds=1000, seed=0):
    """Bootstrap 95% interval for the AUC (resampling issues with replacement)."""
    rng, pairs, out = random.Random(seed), list(zip(scores, labels)), []
    while len(out) < rounds:
        draw = [rng.choice(pairs) for _ in pairs]
        try:
            out.append(auc(*zip(*draw)))
        except ValueError:
            continue
    out.sort()
    return out[int(0.025 * rounds)], out[int(0.975 * rounds) - 1]


def outcome_population(rows):
    """Closed Copilot PRs, one row per issue; an issue whose PRs disagree on the outcome is dropped."""
    by_issue = {}
    for r in rows:
        if r["agent"] == "Copilot" and r["state_pr"] == "closed":
            by_issue.setdefault(r["issue_id"], []).append(r)
    return [v[0] for v in by_issue.values() if len({r["merged"] for r in v}) == 1]


def stratified_sample(population, per_class, seed):
    rng = random.Random(seed)
    out = []
    for outcome in ("True", "False"):
        group = sorted((r for r in population if r["merged"] == outcome), key=lambda r: r["issue_id"])
        out += rng.sample(group, per_class)
    return out


def _paper_issue(row):
    # GitHub has no Linear priority or links: priority is set to High and relations left 0 so the Linear-only rules
    # cannot decide the outcome; the per-dimension and judge-only figures in the summary isolate the judge anyway.
    return ir.Issue(f"{row['repo_key']}#{row['number_issue']}", row["issue_id"], row["title_issue"] or "",
                    row["body_issue"] or "", 2, [], None, 0)


def _read_csv(path):
    csv.field_size_limit(10 ** 9)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_outcomes(data_csv, out_path, llm, per_class=100, seed=190):
    """Score a stratified sample, one JSON line per issue; resumable — already-scored issues are skipped."""
    done = set()
    if os.path.exists(out_path):
        with open(out_path) as f:
            done = {json.loads(line)["issue_id"] for line in f if line.strip()}
    sample = stratified_sample(outcome_population(_read_csv(data_csv)), per_class, seed)
    with open(out_path, "a") as out:
        for row in sample:
            if row["issue_id"] in done:
                continue
            rec = {"issue_id": row["issue_id"], "pr_id": row["pr_id"], "merged": row["merged"] == "True",
                   "body_len": len(row["body_issue"] or "")}
            try:
                raw, product = _raw_and_product(_paper_issue(row), llm)
                rec.update(raw=raw, total=product.total, scores={d: s.score for d, s in product.scores.items()},
                           sources={d: s.source for d, s in product.scores.items()})
            except (ir.ScorerInvalid, ir.ScorerUnavailable) as e:
                rec.update(error=str(e))
            out.write(json.dumps(rec) + "\n")
            out.flush()


def _raw_and_product(issue, llm):
    """ONE judgement of every dimension (rules off = the judge's own view), then the scorer's rules applied to the
    same judgement = the product's total. Both are measured from the same call."""
    dims = judgeable(issue)
    messages, _ = ir.build_messages(issue, dims)
    scores, _, model = ir.judge(llm, messages, dims)
    raw = {d: ir._supported(s, issue.description) for d, s in scores.items()}
    product = ir._combine(issue, ir.issue_kind(issue), ir.plan(issue), raw, None, model, False)
    return {d: s.score for d, s in raw.items()}, product


def summarize_outcomes(out_path, rubric_csv=None):
    """AUC (with a bootstrap 95% interval) of every predictor against the merge outcome, on the scored records."""
    with open(out_path) as f:
        recs = [json.loads(line) for line in f if line.strip()]
    ok = [r for r in recs if "error" not in r]
    labels = [r["merged"] for r in ok]
    series = {**_our_series(ok), **(_paper_series(ok, rubric_csv) if rubric_csv else {})}
    report = {"scored": len(ok), "errors": len(recs) - len(ok), "merged": sum(labels), "auc": {}}
    for name, vals in series.items():
        report["auc"][name] = [round(auc(vals, labels), 3)] + [round(x, 3) for x in auc_interval(vals, labels)]
    return report


def _our_series(ok):
    series = {"our product total": [r["total"] for r in ok],
              "our judge, rules off (mean)": [sum(r["raw"].values()) / len(r["raw"]) for r in ok],
              "issue length (shorter = higher)": [-r["body_len"] for r in ok]}
    for dim in sorted({d for r in ok for d in r["raw"]}):
        series[f"our judge: {dim}"] = [r["raw"].get(dim, 0) for r in ok]
    return series


def _paper_series(ok, rubric_csv):
    paper = {row["pr_id"]: row for row in _read_csv(rubric_csv)}
    series = {"paper 32-criterion mean": [_rubric_mean(paper.get(r["pr_id"])) for r in ok]}
    for crit in ("scope", "context_guidance"):              # the paper's strongest positive single criteria
        series[f"paper {crit}"] = [_num((paper.get(r["pr_id"]) or {}).get(crit)) for r in ok]
    return series


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _rubric_mean(row):
    if not row:
        return 0
    vals = []
    for k, v in row.items():
        if k in ("pr_id", "issue_id"):
            continue
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            pass
    return sum(vals) / len(vals) if vals else 0


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
    o = sub.add_parser("outcomes", help="score a sample of the arXiv 2512.21426 issues; AUC vs merged")
    o.add_argument("data_csv", help="pr_prediction_from_issues/data/all_data_clean.csv")
    o.add_argument("--out", required=True, help="JSON-lines results (resumable)")
    o.add_argument("--rubric-csv", help="pr_prediction_from_issues/data/final_scores.csv (the paper's own scores)")
    o.add_argument("--per-class", type=int, default=100)
    o.add_argument("--seed", type=int, default=190)
    o.add_argument("--summary-only", action="store_true")
    g = sub.add_parser("agreement")
    g.add_argument("files", nargs="+")
    g.add_argument("--model-b", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "snapshot":
        snapshot(args.ids, args.dir, ir.Linear(os.environ.get("LINEAR_API_KEY")))
        return 0
    if args.cmd == "outcomes" and args.summary_only:
        print(json.dumps(summarize_outcomes(args.out, args.rubric_csv), indent=1))
        return 0
    llm = ir.litellm_client(os.environ)
    if args.cmd == "outcomes":
        run_outcomes(args.data_csv, args.out, llm, args.per_class, args.seed)
        print(json.dumps(summarize_outcomes(args.out, args.rubric_csv), indent=1))
        return 0
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
