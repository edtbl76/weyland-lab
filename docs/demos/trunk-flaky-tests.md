# Demo: CI test results in Trunk, flaky tests in Linear (B189)

Every pipeline's tests land in Trunk Flaky Tests with their history, and a flaky or broken test becomes a Linear issue in
Weyland Auto-Filed ([runbook](../runbooks/trunk-flaky-tests.md), [flow](../diagrams/flow-trunk-flaky-tests.md),
[verdict](../concepts/test-visibility.md)). Part 1 was RUN 2026-11-06. Part 2 is the first real pipeline after the owner
adds the Woodpecker secret.

## 1. Trial and rehearsal (RUN 2026-11-06)

| Check | Result |
|---|---|
| All 1,208 bats tests uploaded (JUnit from CI's own bats image) | ingested; per-test history on every test |
| A pass, fail, pass sequence on one test | stays Healthy under the default monitors (they need 5 failures a day, or a retry) |
| Create ticket on a test, with the Linear connection set to Weyland Auto-Filed + `trunk-flaky` | **EMA-335**: project Weyland Auto-Filed, label `trunk-flaky`, assignee ed (read back from the Linear API) |
| The same, from the modal's first open | **EMA-334**: no project, no label, no assignee. The modal shows the saved defaults empty on first open (Trunk bug, reported). `check-linear-sync.sh` failed on it, "OPEN ISSUES WITH NO PROJECT" |
| CLI contract (variant `b189-probe`) | landed and green: exit 0; landed with a failed test: **exit 1**; bad token: exit 70 + `Error Encountered`; no files: exit 70; no CA bundle: hung until killed |
| `trunk-upload.sh` in `alpine:3.20`, the exact CI step | downloaded 0.16.1, sha256 OK, uploaded the `python` lane's 20 reports: **1,680 results, exit 0** |
| Real lanes writing JUnit | python 20 reports; shell 1,235 cases; java 7 Surefire reports (harvested); swift 11 cases with `--parallel` (none without it, which the lane now reports) |
| golden-path report with `<`, `&` and a control character in a log | parses; Trunk's CLI accepts it |

## 2. The first real pipeline (after the owner adds `trunk_org_token`)

Trigger a full pipeline (no vars: every lane plus golden-path-smoke), then read the step:

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && set -a && . scripts/.env && set +a && woodpecker-cli pipeline create edtbl76/weyland-lab --branch main
```

Expect, in the `trunk-upload` step's log: one `<variant>: uploaded` line each for `python`, `shell`, `java`, `kotlin`,
`scala`, `php`, `swift` and `golden-path`, then `OK — 8 variant(s) uploaded`. In Trunk, the `bats` collection shows those
variants with the run's results. In Linear, nothing new unless a monitor fires; any issue Trunk files must be in Weyland
Auto-Filed with `trunk-flaky`, and `check-linear-sync.sh` stays OK.
