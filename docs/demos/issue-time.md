# Demo — time per Linear issue: agent session time, lead and cycle time (B185 lane 1)

How long did an issue take, when the agents do the work? The B62 producer attributes each Claude Code session's active
time and tokens to the issue it was working on, and `issue_time_report.py` joins that with the B194 Linear snapshot.
Rules, limits and commands: [runbooks/issue-time.md](../runbooks/issue-time.md). All RUN 2026-10-12 on rogueone.
The view is the Port **Time per Issue** dashboard (UI walkthrough below); the CLI is `scripts/issue-time.sh`.

## Sequence diagram
See [../diagrams/flow-issue-time-attribution.md](../diagrams/flow-issue-time-attribution.md).

## Prerequisites
`mc` with the `weyland` alias (read on `ai-sessions` and `linear-backup`). No secrets are read by the report.

## CLI walkthrough

**1. Refresh the session summaries** (what `ai-session-producer.timer` runs every 4 h):
[rogueone]
```
systemctl --user start ai-session-producer.service
```
`Result=success`; the journal ends with one `mc mirror` line per summary (`… .json -> weyland/ai-sessions/… .json`).
Each attributed summary carries `issues{}`, `unattributed`, `subagents` and `"usage_counted": "per-message"`.

**2. Report time per issue** (RUN 2026-10-13):
[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-time.sh
```
```
issue      backlog   agent_h sessions  lead_d cycle_d     out_tok
EMA-139    B119         21.4        2    51.5    11.1   2,375,120
EMA-238    B180         13.3        1     5.9     1.4     300,862
EMA-240    B182         12.2        2     9.7     9.6     902,469
…
EMA-237    B179          3.8        1    18.2     3.0     285,520
EMA-243    B185          1.2        1       -       -     154,133
```
Exit 0; 35 issues. **B179 / EMA-237 shows 3.8 h** (the acceptance check: non-zero), and, with the 2026-10-13
snapshot that records its close, lead 18.2 d and cycle 3.0 d. B119's 21.4 h is real and sticky: a 5-day Linear
walk-through that prompts kept naming (runbook, Limits). `--json` prints the same rows as JSON.

**2b. Push to Port** (what the producer runs every 4 h; RUN twice in a row 2026-10-13, both exit 0):
[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-time.sh --port
```
```
port: 35 issue_time entities upserted and read back, 0 stale deleted; dashboard time_per_issue upserted
port: 1 without a linearIssue in Port: EMA-206
```

**3. What the rules corrected, on the same data** (before → after, each a fix with a regression test):

| Check | Before | After |
|---|---|---|
| EMA-292 (an attended session ran `issue-readiness.sh EMA-292` to check the queue) | 3.5 h | 0.1 h — the conveyor run itself |
| Tokens in one session (one record per content block, usage repeated) | 14,304,323 | 5,215,882 counted once per message |
| Subagent logs (`<session>/subagents/`) | not read | 46 logs, tokens to the issue current at their start |
| EMA-209 (B152 named 10 days after it closed) | cycle −10.6 d | cycle `-` (no start known before completion) |

**4. Negative cases — never an empty or partial table, never a half push** (each exit 2, reason on stderr):
[rogueone]
```
ISSUE_TIME_PORT_ENV=/nonexistent bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-time.sh --port; echo "exit=$?"
```
```
issue-time: Port credentials not found (/nonexistent)
exit=2
```
`bash scripts/issue-time.sh --bogus` → `usage: issue-time.sh [--json | --port]`, exit 2. Before the fixes, a Port
404 on one relation (EMA-206) and a 422 on the second run's dashboard update each stopped the push with exit 2 —
found live, now covered by tests. The report on its own:
[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/issue_time_report.py --sessions /home/edwardmangini/.cache/ai-sessions --issues /home/edwardmangini/.claude/jobs/de8fed56/tmp/bad.gz; echo "exit=$?"
```
```
issue_time_report: cannot read Linear snapshot /home/edwardmangini/.claude/jobs/de8fed56/tmp/bad.gz: Expecting value: line 1 column 1 (char 0)
exit=2
```
A directory with no summaries → `no session summaries in …`, exit 2. A `.json` that is not a summary →
`cannot read session summary …`, exit 2 (this case crashed with exit 1 on the first run; fixed and tested).

## UI walkthrough — Port (UAT)

1. Open `https://app.port.io` → **Catalog** sidebar → **Time per Issue**.
   Confirm: the page loads with three number cards and a table, no widget error.
2. **Agent hours (all issues)** shows a non-zero total; **Issues with agent time** shows 35 (the count `--port`
   printed); **Average cycle time (days)** shows a number.
3. In the **Time per issue** table, confirm the first row is **EMA-139 · B119** with **21.4** agent hours (sorted by
   agent hours, most first), and find **EMA-237 · B179** with **3.8**.
4. Click **EMA-237 · B179**, then its **Linear issue** relation. Confirm it opens the Linear issue EMA-237 in Port,
   and that issue's page lists the Issue Time entity under related entities.
5. Find **EMA-206**: it has agent hours but an empty **Linear issue** relation (Port's Linear integration has no
   entity for it) — the expected state, named by the push.

## Cleanup
The table and `--json` are read-only: they write `/home/edwardmangini/.cache/linear-issues.json.gz` (overwritten each
run) and nothing in the repo. `--port` keeps a standing data product, not demo data: 35 `issue_time` entities and the
`time_per_issue` dashboard, rewritten on every run. To retire it, remove the producer's `--port` step, then on rogueone
delete the page and the blueprint (its entities go with it):
```
cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a && tofu destroy -target=port_blueprint.issue_time
```
and delete the dashboard in Port (Catalog → Time per Issue → … → Delete), then `pages/time_per_issue.json` from git.
