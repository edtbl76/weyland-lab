# Runbook: the SDD framework bake-off (B86)

Measures spec-driven development frameworks against plain Claude Code on lab tasks. Verdict and method:
[concepts/spec-driven-frameworks.md](../concepts/spec-driven-frameworks.md). Harness design: `eval/sdd-bakeoff/README.md`.
**On-demand only:** a full run spends real model usage (the 2026-11 bake-off was 72 implementation runs, 37 follow-on
changes and 42 reviews), so it is never wired into CI or a schedule. Check weekly usage (`/status`) before a batch.

The code is in the repo (`eval/sdd-bakeoff/`, the `C` root). Everything a run produces lives in the work dir
(`SDD_BAKEOFF_HOME`, default `/home/edwardmangini/sdd-bakeoff`, the `B` root), outside the repo, because the sandbox
denies trials any read of `~/IdeaProjects`.

## Pick a framework for a project (the selector, B86.1)

Give it a prompt or a PRD; it recommends a spec-driven framework, or none, with its reasons. An LLM only extracts a
fixed feature record from the document; the rules in `scripts/sdd-selector-rules.yaml` decide, each citing the bake-off
evidence it rests on ([flow](../diagrams/flow-sdd-selector.md)). The document is read on the **private lane**
`wl-private-rag`: LAN Ollama only, no fallback (B234), so a private PRD never leaves the LAN. It uses its own virtual
key, `SDD_SELECTOR_LITELLM_KEY` ([model-gateway.md](model-gateway.md) § 1d).

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && LITELLM_API_BASE=http://192.168.1.243:30400 python3 /home/edwardmangini/IdeaProjects/weyland/scripts/select_sdd_framework.py /home/edwardmangini/IdeaProjects/weyland/scripts/tests/fixtures/sdd-selector/brownfield-recurring-prd.md
```

That runs it on a sample PRD (expected: `Pick: OpenSpec`, the example below). For your own document, make the last
argument that file's absolute path. Use `-` in its place to read stdin, and add `--json` for the machine-readable report. To decide from a feature
record you wrote yourself, with no model call (free), use `--features <record.json>`.

- **Reads:** 3, about 25 s each on rogueone. A field counts only when all three agree; otherwise it is `unknown` and
  listed as read inconsistently. The call loads `gpt-oss:20b` on rogueone, so the operator's model reloads on its next
  call.
- **Exit codes:** `0` means a recommendation. `2` means no recommendation: no key, no `LITELLM_API_BASE`, the model is
  unreachable, an answer is malformed, or the document is empty. **Never a default pick on failure.**
- **The report:** the pick and the runner-up; the rule that fired, with its evidence and trial count; the cost band of
  the nearest measured task; caveats for facts no trial covered; and the facts read as unknown, which are what to
  clarify.

Example (RUN 2026-11-02, `scripts/tests/fixtures/sdd-selector/brownfield-recurring-prd.md`):

```
Pick: OpenSpec
Runner-up: plain Claude Code (no framework)
Why (rule repeated-change, 25 trial(s)): the area will keep changing: OpenSpec is the cheapest framework on every measured task, and framework documents make each later change about 12% cheaper, so OpenSpec's extra cost pays back after about 4 later changes
  evidence: docs ablation: 13 pairs, follow-on cost x1.12 without the documents, exact sign-flip p = 0.04 (analysis.txt)
  evidence: trial table: OpenSpec the cheapest framework on small, brown, green and vague (cells.tsv)
Cost band: nearest measured task 'small': this pick $0.87 median, 3/3 passed; plain Claude Code $0.48
Features: {"change_kind": "change_existing", "size": "small", "problem_settled": "settled", "expected_change": "recurring", "teams": "one", "risk": "normal", "existing_specs": "none", "named_framework": "none"}  (rules v1)
```

**Measured stability (2026-11-02):** 8 documents, each run twice: the four B86 task briefs and the four fixtures in
`scripts/tests/fixtures/sdd-selector/`.
- The **pick was the same on both runs, 16 of 16**, and it was the one the evidence supports for every document.
- The **feature record was identical for 7 of 8**. The drift: `vague-idea.md` read `expected_change` as `one_off` once
  and `unknown` once.
- Treat the pick as stable, but read the unknowns and caveats, not only the pick.

**For coding agents:** the Bifrost skill `select-sdd-framework` carries this command and how to read the report, so
any agent with the lab's skills (Claude Code, Codex) runs the selector instead of answering from its own opinion. Its
source is `services/weyland-dagster/scripts/register_bifrost_skills.py`; a change there ships with the Dagster image
and is published by that registrar ([mcp-gateway.md](mcp-gateway.md)).

**Changing the rules:** only with new trial evidence. Re-run the bake-off arm (below), regenerate the trial table, and
cite the new runs in the rule. Bump `version:` in the rules file.

## Self-test (free: no agent, no docker inside, no network)

[rogueone]
```
docker run --rm -v /home/edwardmangini/IdeaProjects/weyland:/r:ro -w /r --entrypoint sh bats/bats:latest -c 'apk add --no-cache python3 py3-yaml jq git >/dev/null 2>&1; bats scripts/tests/sdd-bakeoff.bats'
```

It pins cost accounting, the click-through driver's stop rule (with a stub `claude` via `CLAUDE_BIN`), the fail-closed
checks and the exact statistics.

## Prerequisites (work dir)

| Item | Path | Notes |
|---|---|---|
| Toolbox | `B/toolbox/bin/` | node 24.1.0 (OpenSpec needs at least 22.12), bun 1.4.0, uv 0.10.12, promtool 3.5.3, `bats` (bats-core 1.14), `openspec` (1.16.0 under `toolbox/node`) |
| Python venv | `B/toolbox/venv/` | from `/usr/bin/python3` 3.12 (a pyenv venv does not work inside the sandbox): pyyaml, pytest, fastapi, httpx, uvicorn |
| Trial login | `B/claude-config/` | a fresh `CLAUDE_CONFIG_DIR`: no user CLAUDE.md, plugins or memory. **The owner logs it in**; never copy credentials into it. |
| Base snapshots | `B/reference/base-<task>.tar` | `git archive` of the commit before each real fix (commands below) |
| Docker | host | judges and layer-1 quality run in throwaway CI-image containers |

The sandbox (`eval/sdd-bakeoff/sandbox-settings.json`) allows reads of `B/toolbox` only. If you move the work dir,
update its `allowRead` path.

Rebuild a base snapshot (byte-identical to the 2026-11 ones; verified 2026-11-02):

[rogueone]
```
git -C /home/edwardmangini/IdeaProjects/weyland archive --format=tar -o /home/edwardmangini/sdd-bakeoff/reference/base-small.tar b204afb6
```

The others: `base-brown.tar` from `483b2594`, `base-green.tar` from `5052271c` (`build_trials.sh` removes
`services/store-scaler`), and `base-vague.tar` from `97f94d0a`.

## Run a bake-off

1. Build the trial repos (refuses to overwrite one):

   [rogueone]
   ```
   TASKS="small brown green vague" bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/build_trials.sh
   ```

2. Install the frameworks. **This downloads external code** (npm, PyPI via uv, GitHub): ask the owner first, naming
   package, version and destination.

   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/install_frameworks.sh
   ```

3. Run and judge one trial (repeat per task and arm, or use the batch runners below):

   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/rep_job.sh small openspec -r2
   ```

   `rep_job.sh` runs the trial, judges it, flags every `command not found`, and appends one line to
   `B/results/replicates.tsv`. A batch of 20 replicates, 2 at a time, in a seeded order:

   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/run_reps.sh 1
   ```

4. Layer 1 (quality and mutation of the trial's own tests):

   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/quality/run_quality.sh small openspec
   ```

5. Layer 2 (follow-on change by plain Claude Code), then the docs ablation, each with the base check first:

   [rogueone]
   ```
   TASKS="small brown green vague" bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/build_followon.sh
   ```

   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/run_followon.sh small openspec
   ```

   [rogueone]
   ```
   python3 /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/build_nodocs.py
   ```

   [rogueone]
   ```
   BASE_CHECK=1 TRIALS_DIR=trials3 RESULTS_DIR=results3 bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/run_followon.sh small openspec
   ```

   The base check must print `JUDGE: FAIL`. A `PASS` means the answer is already in the repo; don't run that pair.

   [rogueone]
   ```
   TRIALS_DIR=trials3 RESULTS_DIR=results3 bash /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/run_followon.sh small openspec
   ```

6. The statistics (writes `B/results/analysis.txt`; about 3 minutes, every permutation is enumerated):

   [rogueone]
   ```
   python3 /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/analyze.py
   ```

## Before trusting a framework arm

- **Prove its engine ran.** Count its engine calls in the log; a run with the runtime missing still passes.

  [rogueone]
  ```
  python3 /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/engine_calls.py /home/edwardmangini/sdd-bakeoff/results/small-openspec.jsonl 'openspec (new|status|instructions|validate|archive)'
  ```

- **No `command not found`** in `replicates.tsv`, unless it was the agent's own optional tool (`rg`, `parallel`).
- **A run that changed 0 files and passed** is contamination until proven otherwise.
- Archive an invalid run under `B/invalid/<id>-<reason>/` with a `REASON` file, and re-run it. Never delete it.

## Restore the evidence

The results folders ride rogueone's restic backup ([dr.md](../dr.md), row "SDD bake-off evidence"). Trial repos are
not backed up; rebuild them with `build_trials.sh` and `install_frameworks.sh` (above). Restore into a scratch folder,
compare, then copy back what was lost:

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/backup/.env && set +a && restic restore latest --target /home/edwardmangini/restore-sdd-bakeoff --include /home/edwardmangini/sdd-bakeoff/results --include /home/edwardmangini/sdd-bakeoff/results2 --include /home/edwardmangini/sdd-bakeoff/results3
```

[rogueone]
```
diff -r /home/edwardmangini/sdd-bakeoff/results /home/edwardmangini/restore-sdd-bakeoff/home/edwardmangini/sdd-bakeoff/results
```

## Add a framework, or a new version of one

1. Pick a new arm name. A version of an existing framework gets its own name, as `aidlc211` did for AI-DLC 2.11.2.
2. Install it with its own installer at an exact version, as commit 2 of each trial repo. Add a case to
   `install_frameworks.sh`, or a builder like `build_aidlc211.sh` when the install is a copy.
3. Add the arm's lead prompt to `run_trial.sh`, and add the arm to `ARMS` in `analyze.py` and `ORDER` in `summarize.py`.
4. **Pilot one trial first** and read its log. Check that the engine ran and the runtimes are present, and whether it
   accepts an unattended answer. AI-DLC 2.11 does not, so it needs the click-through driver.
5. Run the 12 runs (4 tasks x 3), layer 1, the follow-ons and the ablation. Then re-run `analyze.py`, and
   `cell_table.py` for the concept doc's trial table (add the arm's label to `LABEL` there).

**AI-DLC versions:** the lab repo stays on 2.6.18. Every other version is its own pinned project folder; see
[aidlc-workflow.md § Version policy](aidlc-workflow.md#version-policy-the-lab-stays-on-2618-other-versions-live-beside-it-decided-2026-11-02-b86).
