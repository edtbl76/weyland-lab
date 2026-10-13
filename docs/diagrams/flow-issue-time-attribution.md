# Flow: time per Linear issue — attributing agent sessions (B185 lane 1, 2026-10-12)

The B62 producer on rogueone parses each Claude Code session and attributes its active time and tokens to the issue
the session was working on; `issue_time_report.py` joins that with the B194 Linear snapshot for lead and cycle time.
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
    participant R as issue_time_report.py
    participant S as MinIO linear-backup (B194 snapshot)

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
    O->>S: mc cp newest issues.json.gz
    O->>R: --sessions ~/.cache/ai-sessions --issues …
    R->>C: read summaries (none, unreadable, or none attributed → exit 2)
    R->>S: read snapshot (unreadable or empty → exit 2)
    Note over R: Bnnn → EMA by title prefix (unarchived wins, still ambiguous → unmapped)
    Note over R: lead = completed − created
    Note over R: cycle = completed − min(startedAt, first agent activity ≤ completed)
    R-->>O: table, most agent time first (exit 0)
```
