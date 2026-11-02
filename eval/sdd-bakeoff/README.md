# SDD framework bake-off harness (B86)

Measures spec-driven development frameworks against plain Claude Code on the lab's own work: each framework installed
by its own installer, the same tasks, model, caps and sandbox, and every outcome judged by a hidden reference judge.
Results and verdict: [docs/concepts/spec-driven-frameworks.md](../../docs/concepts/spec-driven-frameworks.md).
How to run it, add a framework or a version: [docs/runbooks/sdd-frameworks.md](../../docs/runbooks/sdd-frameworks.md).

## Two roots

| Root | What | Where |
|---|---|---|
| `C`, the code | these scripts, `quality/`, task briefs, hidden judges, sandbox + MCP config | this directory (in git) |
| `B`, the work dir | trial repos, results, the toolbox (runtimes, promtool, bats-core), the trial login (`claude-config/`), base snapshots, reference solutions, `invalid/` archives | `$SDD_BAKEOFF_HOME`, default `/home/edwardmangini/sdd-bakeoff` |

Trial repos must stay **outside** the lab repo: the sandbox denies every trial any read of `~/IdeaProjects`, so a trial
can never see the real solution. Binaries are too large for git and live in `B/toolbox/`.

## Layout

```
C (eval/sdd-bakeoff/)
  build_trials.sh       trials/<task>-<arm>[-rN] from B/reference/base-<task>.tar (git archive of the pre-fix commit)
  install_frameworks.sh BMAD / OpenSpec / Spec Kit by their own installers at the pinned versions, as commit 2
  build_aidlc211.sh     the AI-DLC 2.11.2 arm: base committed, then the copy-channel upgrade as commit 2
  run_trial.sh          ONE headless trial; the aidlc211 arm gets the click-through driver
  judge_trial.sh        the hidden judge for a round-1 trial (docker, CI images)
  rep_job.sh run_reps.sh  replicates: run + judge + a locked line in results/replicates.tsv, 2 at a time, seeded order
  build_followon.sh run_followon.sh  layer 2: a follow-on change by plain Claude Code (BASE_CHECK=1 judges the base)
  build_nodocs.py       docs ablation repos (framework documents removed, rebuilt from the follow-on BASE commit)
  quality/              layer 1: ruff, lizard, radon, AST mutation of the trial's own tests (run_quality.sh)
  select_defects.py build_review.py run_review.sh score_reviews.py   spec-as-oracle v1 (single-site defects)
  select_intent.py build_review2.py                                    spec-as-oracle v2 (intent defects; ORACLE=2)
  summarize.py analyze.py   run stats; the exact stratified statistics -> B/results/analysis.txt
  cell_table.py         the per-cell trial table (medians over each cell's runs) -> B/results/cells.tsv + Markdown
  reference/            task-<task>.md (round 1), task2-<task>.md (follow-on), judge*-<task>/ (hidden judges)
  sandbox-settings.json no-mcp.json   the sandbox and the empty MCP config every trial runs with
```

One-off scripts kept for the record: `run_all.sh` and `run_vague.sh` (round 1), `run_followons.sh`, `rejudge_vague.sh`,
`redo_openspec_node18.sh` with `run_openspec_redo.sh` and `redo_job.sh` (the Node 18 redo), `run_rest.sh` (batch 2,
ablation and oracle v1), and `run_aidlc211.sh`.

## Rules the harness enforces (each learned from a failure in the bake-off)

- **Prove the engine ran.** A trial whose framework runtime is missing still passes by working around it. `rep_job.sh`
  and `run_all.sh` flag every `command not found`; check engine calls before trusting a framework arm.
- **Judge the base.** A derived repo built from a working tree carries the previous agent's answer. Build it from a
  commit, then require the base to FAIL its judge (`BASE_CHECK=1 run_followon.sh`) before an agent runs on it.
- **Fail closed.** No own tests found is never "own tests pass"; a review with no `DEFECT LINE` is a miss; a missing
  judge file never excludes a pair.
- **Cost is session-cumulative.** `total_cost_usd` and `modelUsage` accumulate over the whole session, also across
  `--resume`; take the last result. Turns and durations are per process; sum them.
- **Stop the driver on a final status.** The click-through driver stops on `TRIAL DONE`, on a `TRIAL BLOCKED` that is not
  a gate question, and on a reply that changes nothing; stats count only up to the first final status.

Tests: `bats scripts/tests/sdd-bakeoff.bats` (no agent, no docker, no network).
