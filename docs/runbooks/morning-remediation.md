# Morning remediation (B243)

Each morning at 05:30 NY a rogueone user timer collects what broke overnight, tries to fix what is safe to fix, and
reports it, so the owner starts the day with "this WAS broken, here is what was tried" instead of "this is broken".
Linear: EMA-342. Schedule: [schedules.md](../schedules.md) (05:30, node systemd). Everything runs on **rogueone**.

## What one run does

1. **Collect (read-only)** — `scripts/lib/morning_collect.py`, the last 24 h:

   | Source | Read through | One item per |
   |---|---|---|
   | `ci` | Woodpecker API (`WOODPECKER_SERVER`/`_TOKEN`): failed pipelines, failed steps (not `killed` ones), the step's log tail | workflow/step; a failure a later green pipeline superseded is dropped |
   | `alerts` | Prometheus `ALERTS` at the `prometheus-lan` NodePort (`http://mother:30909`): every critical, plus `KubeJobFailed`, `ScheduledJobFailed`, `ScheduledJobStale`, `ScheduledBackupFailed` | CronJob, named from the failed Job's ownerReference (so a hand-started `<cj>-manual-<ts>` Job is `<cj>`); all of a CronJob's alerts merge, with the newest failed Job's log tail. Dropped when the CronJob's `lastSuccessfulTime` is newer than the failure (failed Jobs keep alerting for their 72 h TTL) or the CronJob no longer exists (2026-11-25) |
   | `dagster` | `dagster_runs.py --json-since` piped into `deploy/dagster-user-code` | failed run; runs the runner itself started (tag `weyland/started-by=morning-remediation`) are marked agent-caused |
   | `glitchtip` | a read-only ORM query in `deploy/glitchtip-web`'s Django shell (`IssueIndex`) | unresolved issue seen in the window (new or recurring) |
   | `incidents` | Linear GraphQL (`LINEAR_API_KEY_RO`), project **Weyland Auto-Filed** | incident filed in the window and still open (canceled or done ones are skipped) |
   | `dependabot` | `gh api repos/edtbl76/<repo>/dependabot/alerts` for each `status: active` repo in `repos.yaml` | new high or critical alert |

   A source that cannot be read is reported **NOT CHECKED** with the reason, never as "nothing broke". Evidence is
   scrubbed of secret-shaped text before it can reach a prompt or a report.
2. **Triage** — one headless `claude -p` per item, in a detached worktree, with **read-only tools** (Read, Grep,
   Glob), answering a JSON schema: classification (transient / real / unknown), diagnosis, at most one action
   **from the allowlist**, or a code fix. Evidence is fenced as untrusted data. 15 min per item.
3. **Act**, one of:
   - **An allowlisted action** (transient only), run by `scripts/lib/morning_actions.py`, then **verified**: the new
     CI pipeline, the re-executed Dagster run, the retry Job or the user unit must reach success within 60 min.
     Reported "fixed" only then.
   - **A code fix** (real only): `claude -p` with edit tools only (no Bash) in a new worktree on a local
     `auto-fix/<date>-<slug>` branch, one local commit, then `scripts/local-gates.py` (the TRUSTED checkout's script and
     step list judge the branch) and the SonarQube pre-check on changed Python. Never pushed.
   - **Nothing** — "not fixed", with the diagnosis and what a person must decide.

   Before triage: an agent-caused item is listed separately; a cause seen on an earlier night (7 days) is "recurring,
   not retried". The report never claims more than was verified.
4. **Report** — Slack `#alerts` (`SLACK_WEBHOOK_ALERTS`); a comment on each Auto-Filed incident (`LINEAR_API_KEY`);
   the report file; then the Kuma heartbeat (`KUMA_MORNING_PUSH_URL`, always `up`, the summary and any unchecked
   source in its message). A morning that never ran sends no heartbeat, and that is what pages.

## The allowlist (owner-approved)

`scripts/morning/allowlist.yaml` — approved 2026-11-24 ("yes, approve all four"):

| Action | Command | Parameters |
|---|---|---|
| `ci-retrigger-nightly` | `woodpecker-cli pipeline create edtbl76/weyland-lab --branch main` | none |
| `dagster-reexecute-run` | `dagster_reexecute.py --run <id>` inside `dagster-user-code` (re-execute FROM_FAILURE, tagged) | `run_id` (UUID) |
| `cronjob-rerun` | `kubectl -n <ns> create job --from=cronjob/<cj> <cj>-retry-<yyyymmdd>` | `namespace` (5 allowed), `cronjob` (DNS name) |
| `user-timer-rerun` | `systemctl --user start <unit>` | `unit`: a scheduled rogueone `.service` in `placement.yaml`, never the runner itself |

Each runs from its argv list (never a shell), at most **once per item per night** (the ledger survives a restart).
**Changing the list needs the owner's yes first**, recorded in the file's `approval` fields; the tests in
`scripts/tests/test_morning_actions.py` fail if the runner can execute anything not on it.

## Commands

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/morning-remediation.py --dry-run
```
Collect and print; no model call, nothing sent. `--triage-only` also diagnoses each item and acts on none.
`--post` makes either one deliver the report as well. With no flag it is the real run (what the timer does).

[rogueone]
```
systemctl --user start --no-block morning-remediation.service
```
Run the timer's job now; follow it with `journalctl --user -u morning-remediation -f`.

**Install the timer** (once):

[rogueone]
```
cp /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/systemd/morning-remediation.service /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/systemd/morning-remediation.timer /home/edwardmangini/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now morning-remediation.timer
```

**The heartbeat** is the Kuma push monitor `morning-remediation` (90000 s); create it with
[uptime-kuma.md](uptime-kuma.md) § Create a push monitor, env var `KUMA_MORNING_PUSH_URL`.

## State (`~/.local/state/weyland-morning/`)

| Path | What |
|---|---|
| `reports/<date>.md` | the morning's report (`-dry`, `-triage` for the trial modes) |
| `ledger-<date>.json` | every action attempted that night and its result (the once-per-night guard) |
| `history.json` | each cause's outcome per night (the "recurring" check reads the last 7 days) |
| `worktrees/auto-fix-<date>-<slug>/` | a fix branch's worktree, left for review |
| `run.lock` | one run at a time; a second start exits 3 |

**Backed up** by the rogueone `restic-backup` timer (`backup-paths.conf`, 2026-11-24); restore drill and row in
[dr.md](../dr.md): `restic restore latest --target <scratch> --include "$HOME/.local/state/weyland-morning"`, then `diff -rq`.

**Reviewing a fix branch:** the report names the branch and the worktree. Read `git -C <worktree> show`; if you keep
it, merge or cherry-pick it yourself. To discard it: `git worktree remove <worktree>` and `git branch -D <branch>`.

## The local gate suite

`scripts/local-gates.py` is the canonical "run the FULL local guard suite" command (AGENTS.md): it replays the
secret-free steps of `.woodpecker/platform.yml` (yaml-syntax, repo-guards, shellcheck, shell-tests, complexity-triage,
rego-policies, test-python, test-shell), each in its CI image on a copy of the tree mounted read-only, and names the
CI-only steps. `--root <tree>` checks another tree; `--config <platform.yml>` takes the step list from a trusted file.

## When something is off

| Symptom | Meaning | Do |
|---|---|---|
| Kuma `morning-remediation` down | no run finished in 25 h | `systemctl --user status morning-remediation.service`; `journalctl --user -u morning-remediation` |
| A source says NOT CHECKED | that source could not be read (the reason follows) | fix the access; the other sources were still checked |
| `triage stopped: ...` | the model call failed or exceeded 15 min (subscription limit, hung run) | the item was reported; it is retried by triage the next morning unless it recurs |
| `the action was refused` | the model proposed something the allowlist refuses | correct behaviour: nothing ran |
| `verification failed` | the retry ran and did not succeed | the item needs a person; it will show as recurring tomorrow |
| `the gates did not pass` | the fix branch fails a gate | the branch is kept for review, not reported ready |
| `slack: FAILED` / `linear ...: FAILED` in the journal | a delivery was refused | the report file still has it |
| A second run on the same day refuses every retry, and the fix item says it could not create the worktree | by design: the ledger allows one attempt per item per night, and the branch `auto-fix/<date>-<slug>` already exists | to re-run deliberately (as the seeded test did, 2026-11-24): rename `ledger-<date>.json` and `history.json` to `*.run1`, rename the branch and move its worktree to a `-run1` name, and delete the `<cronjob>-retry-<yyyymmdd>` Job a CronJob retry left (its name is fixed per date) |

## Security design (review of 2026-11-24)

Evidence (log lines, error text, incident text) can be shaped by whatever failed, so: triage reads only; the fix agent
edits only and never runs a command; `claude -p` gets a minimal environment, never `scripts/.env`'s secrets; evidence
is fenced as untrusted in every prompt; tests run only in the gate containers, judged by the main checkout's script;
actions go only through the allowlist's fixed argv with anchored parameter patterns.
