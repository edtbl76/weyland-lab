---
id: ci-watch
title: The CI watch
category: Operations
description: After a push, trigger the lean pipeline and watch it to a terminal state, fixing what fails, until main is green with the Sonar gate passed.
terminal_condition: The pipeline is success with "QUALITY GATE STATUS - PASSED" in the sonar-gate log, or the same step fails twice after a fix (stop and hand off), or three fix-and-retrigger rounds have run.
pacing: One check per expected run time (about 70 minutes for a full lean run), never a short polling timer.
source: docs/runbooks/woodpecker.md (Pipelines; weyland image CI to CD), docs/runbooks/ship-images.md (When the ship stops at the SonarQube gate)
---

## Prompt

The owner has pushed to main. Get the lean CI pipeline green.

1. Trigger it with the canonical command in `docs/runbooks/woodpecker.md` (`woodpecker-cli pipeline create
   edtbl76/weyland-lab --branch main`, creds from `scripts/.env`). Never wait for the nightly cron.
2. Check in once per expected run time, not on a short timer. Each check: list every step that is not `success`.
   Read the step's log, not just its state.
3. When a step fails, prove the layer before fixing: read the failing log lines, reproduce locally in the step's own
   toolchain image where possible, fix, run the full local guard suite (`repo-guards` in `.woodpecker.yml`), and hand
   the owner the push (the owner does all git). Then retrigger.
4. The Sonar gate: read `QUALITY GATE STATUS` in the `sonar-gate` log. If it failed only because a new hotspot is
   unreviewed and the hotspot is genuinely safe, mark it with `scripts/sonar_api.py review-safe <file> "<reason>"`
   and retrigger. Never mark a real finding safe to get green.
5. Report each check in one or two lines: run number, passed/failed step counts, what is next.

Stop when the terminal condition holds. On a repeat failure of the same step after a fix, stop and report the step,
the log lines, and what you tried. Never claim green without reading the sonar-gate log text.
