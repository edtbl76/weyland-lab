# Issue readiness — the lab's own scorer (B190, replaces SpecBot)

Is a Linear issue ready to hand to a coding agent without the agent guessing? `scripts/issue-readiness.sh` scores an
issue on 8 dimensions, prints the breakdown, and keeps ONE comment on the issue up to date. Threshold **80** — the same
bar `AGENTS.md` sets for delegating an issue. It replaces SpecBot (a third-party judge: 25 analyses a month, an opaque
rubric and model, nothing CI could gate on).

| Piece | Where |
|---|---|
| Scorer | `scripts/issue_readiness.py` (logic) · `scripts/issue-readiness.sh` (wrapper: reads `scripts/.env`) |
| Judge | LiteLLM `wl-judge-oss` → Ollama `gpt-oss:20b-judge` on rogueone (gpt-oss:20b, 16K window — `nodes/rogueone/ollama/gpt-oss-20b-judge.Modelfile`). Free, local |
| CI | `.woodpecker.yml` step `issue-readiness` — LEAN (manual) runs only, advisory (`failure: ignore`) |
| Judge eval | `scripts/issue_readiness_eval.py` + issue snapshots in `eval/issue-readiness/issues/` |
| Tests | `scripts/tests/test_issue_readiness.py`, `test_issue_readiness_eval.py` (pytest) · `issue-readiness.bats` |

All commands run on **rogueone**.

## Score an issue

```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh EMA-249
```
Prints 8 dimension scores (each marked `rule` or `llm`), the total, blockers and suggested fixes, and creates or updates
the issue's one comment (`**Issue readiness (weyland scorer)**`). `--no-comment` scores only; `--json` is
machine-readable. Exit **0** READY (total ≥ 80 and no blockers) or skipped · **1** NOT READY · **2** the judge or Linear
was unreachable, or the judge's answer was unusable — **never a guessed score**.

Sweep every open High issue in project Weyland Lab (what CI runs):
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh --sweep
```
The sweep re-scores only an issue whose content changed since its last comment: each comment carries a `digest` of
everything the score depends on (title, description, priority, labels, linked issues, rubric version). Unchanged issues
print `unchanged since last score` and cost nothing. A single-issue run always re-scores.

## How a score is made

1. **Rules first, no model call.** A rule decides what the text can settle:
   | Rule | Score |
   |---|---|
   | No Acceptance criteria section, or only the template placeholder | Acceptance criteria **10** + blocker |
   | No Edge cases section | Edge cases **10** |
   | A Bug (label) with no Repro section | Reproduction **10** + blocker |
   | No dependency named and no Linear link (write `Dependencies: none` if there are none) | Dependencies **15** |
   | No Why / problem statement (an opening paragraph counts) | Objective capped at **50** |
   | No Expected behavior / outcome section | Expected behavior capped at **50** |
   | No Technical context section | Technical context capped at **50** |
   | No Out of scope list | Priority and scope capped at **60** |
   | No priority set | Priority and scope capped at **30** |
   A missing estimate is never penalized (the lab does not use estimates). Reproduction is **n/a** on anything that is
   not a Bug and is left out of the total.
2. **The judge scores the rest** — temperature 0, JSON only, every requested dimension an integer 0-100 (one retry,
   then exit 2). Every score of 50 or more must quote the issue; the CODE checks the quote is really there (most of its
   3-word runs occur in the issue) and caps an unsupported score at 40. Model scores are capped at 90.
3. **Three votes, the median per dimension** — one outlier judgement cannot move a verdict (see § Proving the judge).
4. **Total = the rounded mean** of the applicable dimensions (SpecBot's own formula). READY needs ≥ 80 and no blocker.

## Proving the judge

Re-run all three whenever the judge model, its LiteLLM alias, the prompt or the rubric changes, and record the result
below. The defect test is the one that matters: it is the evidence that the judge reads QUALITY inside a section — the
part no rule can check.

```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && python3 issue_readiness_eval.py defects ../eval/issue-readiness/issues/*.json
```
```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && python3 issue_readiness_eval.py agreement --model-b wl-default ../eval/issue-readiness/issues/*.json
```
Refresh the snapshots (read key is enough):
```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && LINEAR_API_KEY=$LINEAR_API_KEY_RO python3 issue_readiness_eval.py snapshot EMA-195 EMA-233 EMA-237 EMA-242 EMA-243 EMA-249 EMA-252 EMA-254 EMA-255 EMA-256 EMA-257 EMA-258
```
