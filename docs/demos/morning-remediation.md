# Demo — morning remediation: what broke overnight, what was tried, the outcome (B243)

Each morning a rogueone timer collects the night's failures, retries what is safely retryable through an owner-approved
allowlist, writes code fixes to a local branch, and reports. Operate:
[runbooks/morning-remediation.md](../runbooks/morning-remediation.md) · flow:
[diagrams/flow-morning-remediation.md](../diagrams/flow-morning-remediation.md) · Linear EMA-342.

## The seeded test night (RUN 2026-11-24, on demand)

The owner approved five seeds ("All five") and said to run it now rather than wait for 05:30 ("We don't wait"):

| Seed | Source it exercises |
|---|---|
| CronJob `b243-seed` (fails with a fake HTTP 503, passes when re-run) | `alerts` (KubeJobFailed / ScheduledJobFailed) |
| Dagster `b243_seed_job` (fails a first run, passes a re-execution) | `dagster` |
| a test error sent with the GlitchTip runbook's SDK command | `glitchtip` |
| incident EMA-360 filed in Weyland Auto-Filed | `incidents` |
| `scripts/lib/b243_seed_bug.py` (`hours * 50`) and its correct test | `ci` (test-python red) |

**1. Start it the way the timer does.**

[rogueone]
```
systemctl --user start --no-block morning-remediation.service
```

**2. What the report said (run 2, `~/.local/state/weyland-morning/reports/2026-11-24.md`, also posted to Slack `#alerts`):**

| Item | Outcome | Proof in the report |
|---|---|---|
| CI #732 `platform / test-python` | **fix branch ready** | `auto-fix/2026-11-24-ci-platform-test-python` (local, not pushed); full gate suite passed. The commit changes `hours * 50` to `hours * 60` |
| CronJob `weyland/b243-seed` | **fixed by an allowlisted retry** | `cronjob-rerun` → `Job weyland/b243-seed-retry-20261124 succeeded` |
| Dagster run `0ca5f5b8` of `b243_seed_job` | **fixed by an allowlisted retry** | `dagster-reexecute-run` → `Dagster run 289c70bd… succeeded` |
| GlitchTip test error, incident EMA-360 | not fixed: a person decides | each diagnosis named it a B243 seed, not a real fault |
| real: `pr-staleness-check`, `code-scan-suite`, `sonar-scan-repos`, EMA-359 | not fixed: a person decides | cited diagnoses (e.g. GitHub 404 for `edtbl76/Skeets` and `MyBodyGraph`); no unsafe action taken |

Delivery lines in the journal: `slack: sent`, `linear EMA-360: commented (d51ff424…)`, `linear EMA-359: commented
(a700b274…)`, `kuma: pushed`.

## The guards, seen failing

- **Once per item per night.** Run 1 re-executed Dagster run `9154c6bc`; two GlitchTip items about the same run then
  proposed the same action and got `the action was refused: dagster-reexecute-run {'run_id': '9154c6bc…'} was already
  attempted tonight; never twice in one night`. Nothing ran.
- **Nothing is "ready" that the gates did not pass.** In run 1 the fix itself was right, but the Sonar pre-check, run
  from the service's `~`, saw the worktree as a hidden path and scanned 0 files (`sonar_api: precheck scanned 0 files —
  analysed nothing, which is not clean`, exit 2). The report said `not fixed … the gates did not pass`, not "ready".
  Fixed test-first (the pre-check now runs inside the branch tree); run 2 reported it ready.
- **An unreadable source is never quiet.** The first live dry run printed `glitchtip NOT CHECKED: kubectl exit 1 …`
  (a wrong model field), and the report listed it instead of "nothing broke".
- **The gate runner fails by name.** `python3 /home/edwardmangini/IdeaProjects/weyland/scripts/local-gates.py` on a tree
  with a stale placement embed printed `FAIL shell-tests … FAIL test-shell` and `local-gates: FAIL (… 6 of 8 passed)`,
  exit 1; after `embed-placement.sh` it printed `local-gates: PASS (8 steps)`, exit 0.
- **The allowlist refuses what it does not list.** `scripts/tests/test_morning_actions.py`: an unlisted action, a
  parameter off its pattern, an extra parameter, a unit not in `placement.yaml`, and the runner's own unit are each
  refused before anything runs.

## Afterwards

The seeds were removed (files, freshness-rule entries, the `schedules.md` row; EMA-360 canceled). The two runs' local
branches stay for the owner: `auto-fix/2026-11-24-ci-platform-test-python` and its `-run1` twin.
