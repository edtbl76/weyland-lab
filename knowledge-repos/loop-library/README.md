# loop-library/ — the lab's reusable agent loops (B175)

A **loop** is a reusable agent workflow: a prompt with checkpoints and an explicit **terminal condition**, a stopping
rule that keeps it from running away and wasting cycles. These are the workflows the lab already runs again and
again, written down once so any agent (or the owner) runs them the same way. Modeled on the Forward Future loop
library (title · category · description · prompt), plus the terminal condition this library requires.

**This directory is the source of truth.** Each loop is published to Bifrost's Prompt Repository (folder
`loop-library`, prompt `loop-<id>`) so every harness can discover it through the gateway. Edit loops **here**, never
in Bifrost, Langfuse or MLflow: the weekly reconcile overwrites the published copy with a new version from git.

## The loops

| Loop | Category | Stops when |
|---|---|---|
| [ci-watch](ci-watch.md) | Operations | the pipeline is green with the Sonar gate passed, or one step fails twice after a fix |
| [dod-gate](dod-gate.md) | Engineering | all 9 pillars carry evidence or a stated N/A and the tracker agrees, or a pillar needs the owner |
| [issue-readiness-sweep](issue-readiness-sweep.md) | Engineering | every open High issue prints READY, or an issue needs a decision only the owner can make |
| [scan-triage](scan-triage.md) | Engineering | every new finding is fixed, accepted with a reason, or proven false, and the rerun shows no untriaged finding |
| [golden-path-verify](golden-path-verify.md) | Engineering | every golden path prints SMOKE OK, or each failing path is named with its log line |
| [nightly-soak-check](nightly-soak-check.md) | Operations | the soak reaches its target count of clean nights, or a night fails |
| [incident-enrich](incident-enrich.md) | Operations | one summary per firing alert is written, within six tool calls |
| [machine-onboarding](machine-onboarding.md) | Operations | `machine_inventory.py verify <host>` prints OK, or an operator or decision gate is reached |
| [mcp-fleet-debug](mcp-fleet-debug.md) | Operations | every fleet server lists its tools, or the failing layer is proven and the fix named |
| [pr-lifecycle-reconcile](pr-lifecycle-reconcile.md) | Operations | every managed PR has a verdict and every action is taken or handed off |
| [eval-run](eval-run.md) | Evaluation | the latest run is scored and the leaderboard reported, or a job fails twice |

## Entry format

One Markdown file per loop, named `<id>.md`:

```
---
id: <kebab-case, same as the file name>
title: <the loop's name>
category: Engineering | Operations | Evaluation | Content | Design
description: <one line: what it is for>
terminal_condition: <the checkable stopping rule — at least 25 characters, no "when done">
pacing: <optional: how often an unattended run should check in>
source: <optional: the runbook section(s) holding the commands>
---

## Prompt

<the full prompt, pasteable into /loop or any agent>
```

**Commands live in runbooks, not here.** A loop names the runbook section that holds each canonical command, so a
changed command is fixed in one place (`AGENTS.md`: every operational task has one canonical command).

**Pacing matters for cost.** An unattended loop that wakes every few minutes to watch a 70-minute CI run re-sends its
whole context each time. Check in once per expected duration, not on a short timer.

## Checks and publishing

| | Command / place |
|---|---|
| Validate (CI `repo-guards`) | `bash scripts/check-loop-library.sh` — exit 0 valid · 1 an entry is invalid or the bundle is stale · 2 could not read |
| Rebuild the bundle after editing a loop | `bash scripts/embed-loops.sh` (writes `services/weyland-dagster/scripts/loop_library.json`) |
| Publish to Bifrost | Dagster `registrations` group, asset `bifrost_loops_registered` (weekly + on demand), runs `register_bifrost_loops.py` |
| Find a loop | Bifrost UI → Prompt Repository → `loop-library`, or this directory |

The bundle is a generated copy because the Dagster image is built from `services/weyland-dagster/` and cannot read
this directory; the check fails if the bundle drifts from the Markdown, the same pattern as `placement.yaml`.
