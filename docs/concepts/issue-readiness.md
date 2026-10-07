# Issue readiness — what replaced SpecBot, and why it is not an LLM score (B190, 2026-10-06)

## Verdict

| Option | Verdict | Why |
|---|---|---|
| **Rules check of the lab's written standard** (`scripts/issue-readiness.sh`) | **ADOPT** — replaces SpecBot | It does the job SpecBot did here: enforce `AGENTS.md`'s implementation-ready sections per issue kind before delegation. Exact, free, unlimited, under a second, gateable in CI. |
| LLM 0-100 readiness score (our own judge) | **DON'T ADOPT** — built, measured, dropped | No text-based readiness score predicted agent outcomes (AUC ~0.51 on 200 issues). The judge does see quality, but there is no evidence that quality, as judged, matters to the outcome. |
| SpecBot (Linear integration) | **RETIRED** | Same text-only approach as above, no published accuracy, mis-scores sections the text contradicts, 25 checks/month free ($5-19/seat/month beyond), cloud-only, no CI gate. |
| Other free tools (issueready, IssueGauge, RequirementLinter, Atlassian Rovo Readiness Checker, Linear Triage Intelligence) | DON'T ADOPT | GitHub- or Jira-only, alpha, need a paid API key, or a paid Linear plan — and none publishes outcome validation. |

**Re-open only with new evidence:** an outcome dataset where a readiness score predicts agent success on issues like
the lab's. The research harness below re-runs the whole measurement against a new judge in a few hours.

## The job, not the tool

`AGENTS.md` requires every issue an agent drafts to be implementation-ready: beyond Why and Scope it carries
**Technical context**, **Acceptance criteria**, **Edge cases & failure modes** and **Out of scope**. SpecBot was named
as the check before delegating because it caught EMA-240 with none of those (51/100, 2026-09-25). Its 0-100 score was
a stand-in for "meets the lab's standard". The standard is written down — per issue kind in the Linear templates — so
it can be checked exactly. B190 first spent its effort rebuilding and calibrating SpecBot's score; the owner's
question set it right: *"If SpecBot doesn't predict things, why are we focused on it?"*

## Evidence (all 2026-10-06)

### 1. SpecBot scores sections the text contradicts

12 issues scored by both on unchanged text (7 fresh SpecBot runs requested for this). SpecBot gave **Acceptance
criteria 90** and **Edge cases 82** to issues that have neither section (EMA-195, EMA-233, EMA-237, EMA-243 — EMA-243
read in full), and **Technical context 44** to issues that carry a Technical context table (EMA-254/255/256). Its
totals are the plain rounded mean of its 8 dimensions (EMA-240: 51 / 70 / 75 reproduce exactly).

### 2. Judge choice — the defect test

Real issues, one section damaged the way a weak author writes it (concrete criteria → "it works as expected", the
context removed from every section, "Out of scope: nothing in particular"...). A case passes when the judge cuts THAT
dimension by ≥ 20 to ≤ 60. Only sections the judge first rated ≥ 70 count.

| Judge (local, $0) | Caught | Notes |
|---|---|---|
| gpt-oss:20b | **32 / 39 (82%)** | acceptance criteria 6/7 · edge cases 6/6 · problem statement 8/9 · out of scope 6/6 · technical context 4/5 · **end state removed 2/6** |
| qwen2.5:7b | 9 / 38 (24%) | 0/6 vague acceptance criteria, 0/9 problem statements, 0/5 technical context; rated nearly everything 85-90 |
| gemini-2.5-flash (free hosted) | not measured | free daily quota exhausted mid-run (every call HTTP 429); on direct scoring it gave Acceptance criteria 90 to issues with none — the SpecBot pattern |

Two operator flaws were found and fixed on the way: removing one section while the issue states the same thing
elsewhere tests nothing (EMA-254 names its paths in Scope, so deleting only its table rightly left the judge at 90).

### 3. Is the judge idiosyncratic? — agreement with gpt-oss-120b (Groq free tier, fallbacks disabled)

On the dimensions the judge decides (rules excluded), gpt-oss:20b and gpt-oss-120b agree within 15 points on
**44 of 50** scores; mean gap 1.7-7.1 per dimension except Dependencies (15.0).

### 4. Repeatability

At temperature 0 the same issue moved up to **4** points between runs and flipped one verdict (EMA-257: 83 / 83 / 79).
A median of three judgements gave identical totals 3/3 on the 5 issues nearest the threshold.

### 5. The decisive one — does any readiness score predict the outcome?

Data: the replication package of *What Makes a GitHub Issue Ready for Copilot?* (arXiv 2512.21426,
[DaREf-MS/pr_prediction_from_issues](https://github.com/DaREf-MS/pr_prediction_from_issues)) — GitHub issues handed
to Copilot, each with whether the agent's PR was merged, and the paper's own 32-criterion LLM rubric scores. Sample:
200 closed Copilot PRs (100 merged / 100 not, seed 190, one per issue, conflicting outcomes dropped, from 2,104).

| Predictor of "the agent's PR was merged" | AUC | 95% interval |
|---|---|---|
| our judge: expected behavior | 0.571 | 0.499 – 0.648 |
| paper: scope | 0.567 | 0.501 – 0.638 |
| paper: context guidance | 0.536 | 0.461 – 0.618 |
| issue length (shorter = higher) | 0.524 | 0.448 – 0.605 |
| **our judge, all dimensions** | **0.510** | 0.437 – 0.590 |
| **paper's 32-criterion rubric** | **0.508** | 0.427 – 0.586 |
| **our full score (rules + judge)** | **0.506** | 0.429 – 0.583 |
| our other single dimensions | 0.43 – 0.50 | every interval includes 0.50 |

0.50 is a coin flip. Nothing clears it with confidence. The paper's published 0.72 comes from a model that adds
repository history (prior merged PRs is a top feature), not issue text. **Limits:** GitHub issues + Copilot, not the
lab's Linear issues + Claude Code; n = 200 cannot rule out a weak effect (AUC ≈ 0.6).

## Consequences

* `AGENTS.md`'s readiness rule names `scripts/issue-readiness.sh` (must print READY); the Backlog item template's
  "Run @SpecBot" line was replaced (2026-10-07). Uninstalling the SpecBot integration is a Linear settings action.
* The lean-CI step `issue-readiness` checks open High Weyland Lab issues, advisory, under a second.
* The judge builds stay: `wl-judge` → `qwen2.5:7b-operator` (32K) and `wl-judge-oss` → `gpt-oss:20b-judge` (8K) —
  Ollama's 2K / 4K defaults cut long judge prompts silently for every other judge (Langfuse evaluators) too.

## Research harness (re-run when the judge model or hardware changes)

`scripts/readiness_judge.py` (the judge as built — it refuses to post comments) and `scripts/issue_readiness_eval.py`
(`defects` · `agreement` · `outcomes`), issue snapshots in `eval/issue-readiness/issues/`. Commands:
[runbooks/issue-readiness.md](../runbooks/issue-readiness.md) § Research harness.
