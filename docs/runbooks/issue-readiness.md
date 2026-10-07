# Issue readiness — the check that replaced SpecBot (B190)

Is a Linear issue implementation-ready by the lab's standard? `AGENTS.md` requires every issue an agent drafts to
carry, beyond Why and Scope, **Technical context**, **Acceptance criteria**, **Edge cases & failure modes** and **Out of
scope** — per issue kind, the sections of its Linear template. `scripts/issue-readiness.sh` checks exactly that, by
rule, prints **READY** or **NOT READY** with every missing item named, and keeps ONE comment on the issue current.
Run it before delegating an issue — it must print READY. Why it is rules and not an LLM score:
[concepts/issue-readiness.md](../concepts/issue-readiness.md).

| Piece | Where |
|---|---|
| Check | `scripts/issue_readiness.py` (logic) · `scripts/issue-readiness.sh` (wrapper: reads `scripts/.env`) |
| CI | `.woodpecker.yml` step `issue-readiness` — LEAN (manual) runs only, advisory (`failure: ignore`), secret `linear_comment_key` (write) |
| Standard | `REQUIRED` in `scripts/issue_readiness.py` ⇄ the Linear templates (snapshot: `scripts/tests/fixtures/issue-readiness/linear-templates.json`) |
| Tests | `scripts/tests/test_issue_readiness.py` (pytest) · `scripts/tests/issue-readiness.bats` |

All commands run on **rogueone**.

## Check an issue

```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh EMA-249
```
Prints `READY` or `NOT READY` and one `missing:` line per gap, then creates or updates the issue's one comment
(`**Issue readiness (weyland check)**`). `--no-comment` checks only (the read-only key is enough); `--json` is
machine-readable. Exit **0** READY · **1** NOT READY · **2** Linear unreachable, the key missing, or a usage error —
an error is **never** READY.

Every open High issue in project Weyland Lab (what CI runs):
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh --sweep
```

## The standard

| Kind (how it is detected) | Required sections |
|---|---|
| Backlog item (default) | Why · Scope · Technical context · Acceptance criteria · Edge cases & failure modes · Out of scope |
| Bug (label `Bug`) | Observed · Expected · Repro · Evidence · Technical context · Acceptance criteria · Edge cases & failure modes |
| Spike (label `Spike`) | Questions to answer · Constraint gate · Overlap · Technical context · Acceptance criteria · Edge cases & failure modes · Out of scope · Deliverable |
| Bucket (label `Bucket`, or `(bucket)` in the title) | Purpose · Exit criteria |

Every kind also needs the issue's **priority** field set. What counts:

* A section counts when it has real content — not just the template's guidance line or placeholder (`(criterion)`,
  `* (edge case)`, the empty table row), and not a stand-in word (`TBD`, `todo`, `N/A`).
* **Acceptance criteria** need at least one real checkbox or bullet — prose alone is not a pass/fail check.
* Headings may be `##` or a line-opening bold run (`**Acceptance criteria**`, `**Why.** ...`); a heading counts when
  it starts with the section's name, so `Edge cases` satisfies `Edge cases & failure modes`. An opening paragraph
  before any heading counts as the Why (or a Bucket's Purpose).
* An issue created from a template and never filled in is NOT READY with every section listed (tested against the
  real template bodies).

**When a Linear template changes**, change `REQUIRED` with it and refresh the fixture snapshot; the test
`test_every_required_section_is_a_heading_its_template_has` fails if the code demands a heading the template lacks.

## SpecBot — out of the workflow, kept as a backup

`AGENTS.md` and the Backlog item template name this check (changed 2026-10-07). The SpecBot integration stays
**installed as a backup** (owner, 2026-10-07: "until we're confident that our solution is good enough"): `@SpecBot` in an
issue comment still asks it for a second opinion (25 free checks a month; 7 went to B190's calibration in October). It
also still auto-reviews new issues, so the Linear restore drill keeps neutralizing `@mentions`
([linear-backup.md](linear-backup.md)). When the owner is confident, it is uninstalled in Linear → Settings →
Integrations → SpecBot.

## Research harness — the LLM readiness score B190 dropped

Kept so the verdict in [concepts/issue-readiness.md](../concepts/issue-readiness.md) can be re-tested when the judge
model or hardware changes. `scripts/readiness_judge.py` is the judge as built (8 dimensions, quote-checked, median of
votes; it never posts comments); `scripts/issue_readiness_eval.py` measures it. The judge is LiteLLM `wl-judge-oss` →
`gpt-oss:20b-judge` on rogueone (~50 s a judgement: the 20b model does not fit the 16 GB card beside the desktop).
Each run displaces the operator's model from the GPU while it lasts.

The decisive measurement — does a readiness score predict whether an agent's PR is merged? It needs the paper's data
(clone `https://github.com/DaREf-MS/pr_prediction_from_issues` to `/tmp/pr_pred`); ~3 h for 200 issues; resumable:
```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && LITELLM_API_KEY=x LITELLM_API_BASE=http://127.0.0.1:11434/v1 ISSUE_READINESS_MODEL=gpt-oss:20b-judge python3 issue_readiness_eval.py outcomes /tmp/pr_pred/data/all_data_clean.csv --rubric-csv /tmp/pr_pred/data/final_scores.csv --out /tmp/issue-readiness-outcomes.jsonl
```
The defect test (does the judge see a damaged section?) and cross-judge agreement:
```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && LITELLM_API_BASE=http://192.168.1.243:30400 python3 issue_readiness_eval.py defects ../eval/issue-readiness/issues/*.json
```
```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && LITELLM_API_BASE=http://192.168.1.243:30400 python3 issue_readiness_eval.py agreement --model-b wl-default ../eval/issue-readiness/issues/*.json
```
