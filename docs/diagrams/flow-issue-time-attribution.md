# Flow: time per Linear issue — agent sessions and the owner's own time (B185 lanes 1 and 2)

The B62 producer on rogueone parses each Claude Code session and attributes its active time and tokens to the issue
the session was working on; `issue_time_report.py` (run as `scripts/issue-time.sh`) joins that with the B194 Linear snapshot for lead and cycle
time, prints it, and pushes it to Port.
The marker rules are a decision table — why a tool result never switches, why an attended readiness call does not —
so they are drawn here. Runbook: [issue-time.md](../runbooks/issue-time.md).

```mermaid
sequenceDiagram
    participant T as ai-session-producer.timer (rogueone, every 4h :07)
    participant F as ai_session_feeder.py
    participant L as Session logs (~/.claude/projects)
    participant C as ~/.cache/ai-sessions
    participant M as MinIO ai-sessions
    participant O as Owner (by hand)
    participant W as owner_time.py
    participant A as ActivityWatch (127.0.0.1:5600)
    participant K as Clockify API
    participant R as issue_time_report.py
    participant S as MinIO linear-backup (B194 snapshot)
    participant P as Port (issue_time + Time per Issue dashboard)

    T->>F: run
    F->>L: read main log, event by event
    Note over F: human prompt naming ONE id → switch
    Note over F: title CHANGED naming one id → switch
    Note over F: issue-readiness.sh EMA-nnn while nothing current → switch
    Note over F: tool result, assistant text, injected notice → never
    Note over F: gap ≤ 300 s → active minutes to the current issue
    Note over F: usage counted once per message id
    F->>L: read subagents/agent-*.jsonl
    Note over F: tokens → the issue current at the subagent's start, no time added
    F->>C: one summary per session (issues{}, unattributed, usage_counted)
    T->>M: mc mirror (only if the feeder succeeded)
    T->>W: owner_time.py --env-file scripts/.env (lane 2: its failure does not stop the agent push, but fails the unit)
    W->>A: POST /api/0/query/ per day: web events ∩ Chrome active ∩ not-AFK, other windows ∩ not-AFK
    Note over W: a Linear tab → the EMA id in its URL (its title also names the B number)
    Note over W: any other window → its single EMA id, else its single B number, else unattributed
    W->>K: GET /user, then the user's time entries (CLOCKIFY_API_KEY, only that line of .env)
    Note over W: "[EMA-nnn] title" entries, running timers reported not counted, no key → not-configured (never 0)
    W->>W: aw-day-*.json, owner_time.json, resources.jsonl (the trial's CPU/RSS sample), any source unreadable → exit 2 and nothing written
    T->>R: issue-time.sh --port (only if the mirror succeeded)
    O->>R: issue-time.sh (table) or --json, by hand
    R->>S: mc ls, then mc cp the newest issues.json.gz + workflowStates.json.gz (none listed or copy failed → exit 2)
    R->>C: read summaries (none, unreadable, or none attributed → exit 2)
    R->>S: read snapshot (unreadable or empty → exit 2)
    Note over R: Bnnn → EMA by title prefix (unarchived wins, still ambiguous → unmapped)
    Note over R: lead = completed − created
    Note over R: Linear start = startedAt, else first move into a started-type state (as the dbt mart)
    Note over R: cycle = completed − min(Linear start, first agent activity ≤ completed)
    R->>W: read owner_time.json (absent → owner columns unknown, said aloud, unreadable → exit 2)
    R-->>O: table, most agent time first (exit 0)
    R->>P: upsert one issue_time entity per issue, related to its linearIssue when Port has it
    R->>P: read every entity back (a mismatch → exit 1), delete stale ones
    R->>P: upsert the dashboard from tofu/port/pages/time_per_issue.json
    Note over P: Catalog sidebar, Time per Issue
```
