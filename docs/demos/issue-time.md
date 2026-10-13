# Demo — time per Linear issue: agent session time, lead and cycle time (B185 lane 1)

How long did an issue take, when the agents do the work? The B62 producer attributes each Claude Code session's active
time and tokens to the issue it was working on, and `issue_time_report.py` joins that with the B194 Linear snapshot.
Rules, limits and commands: [runbooks/issue-time.md](../runbooks/issue-time.md). All RUN 2026-10-12 on rogueone.
There is no UI — the CLI walkthrough is the whole demo (the Port `ai_session` ingest is deliberately off,
`docs/schedules.md`).

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

**2. Report time per issue:**
[rogueone]
```
mc cp -q "weyland/linear-backup/snapshots/$(mc ls weyland/linear-backup/snapshots/ | tail -1 | awk '{print $NF}')issues.json.gz" /home/edwardmangini/.cache/linear-issues.json.gz && python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/issue_time_report.py --sessions /home/edwardmangini/.cache/ai-sessions --issues /home/edwardmangini/.cache/linear-issues.json.gz
```
```
issue      backlog   agent_h sessions  lead_d cycle_d     out_tok
EMA-139    B119         21.4        2    51.5    11.1   2,375,120
EMA-238    B180         13.3        1     5.9     1.4     300,862
EMA-240    B182         12.2        2     9.7     9.6     902,469
EMA-225    B138         11.3        1     8.2     3.2   1,104,793
EMA-221    B164         10.3        1     4.0     1.4   1,221,749
…
EMA-237    B179          3.8        1       -       -     285,520
EMA-243    B185          0.4        1       -       -      69,969
```
Exit 0; 35 issues, 126.5 agent hours, 1.8 % of active time unattributed. **B179 / EMA-237 shows 3.8 h** (the acceptance
check: non-zero). Its lead time is `-` because the 05:20 snapshot predates its close that day. B119's 21.4 h is real
and sticky: a 5-day Linear walk-through that prompts kept naming (runbook, Limits).

**3. What the rules corrected, on the same data** (before → after, each a fix with a regression test):

| Check | Before | After |
|---|---|---|
| EMA-292 (an attended session ran `issue-readiness.sh EMA-292` to check the queue) | 3.5 h | 0.1 h — the conveyor run itself |
| Tokens in one session (one record per content block, usage repeated) | 14,304,323 | 5,215,882 counted once per message |
| Subagent logs (`<session>/subagents/`) | not read | 46 logs, tokens to the issue current at their start |
| EMA-209 (B152 named 10 days after it closed) | cycle −10.6 d | cycle `-` (no start known before completion) |

**4. Negative cases — the report never prints an empty or partial table** (each exit 2, reason on stderr):
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

## Cleanup
Read-only. It writes `/home/edwardmangini/.cache/linear-issues.json.gz` (overwritten each run) and nothing in the repo.
The producer run writes the same summaries its timer writes.
