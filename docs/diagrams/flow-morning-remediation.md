# Flow: morning remediation (B243)

Each morning at 05:30 NY a rogueone user timer collects what broke overnight, decides per item, acts only within the
owner-approved allowlist, and reports. Operate: [runbooks/morning-remediation.md](../runbooks/morning-remediation.md).
Proven on the seeded test night of 2026-11-24 ([demos/morning-remediation.md](../demos/morning-remediation.md)).

```mermaid
flowchart TD
    T["morning-remediation.timer<br/>05:30 NY, rogueone"] --> C["collect (read-only, last 24 h)<br/>ci · alerts · dagster · glitchtip · incidents · dependabot"]
    C -->|a source cannot be read| NC["NOT CHECKED + reason<br/>(never 'nothing broke')"]
    C --> M["one item per cause<br/>per CronJob, per Dagster job (owns every run id),<br/>GlitchTip run reports folded into their run,<br/>CI failures a later green run superseded dropped"]
    M --> A{"started by the runner itself?"}
    A -->|yes| AG["caused by an agent<br/>(listed apart, never acted on)"]
    A -->|no| R{"same cause in the last 7 days?"}
    R -->|yes| RC["recurring, not retried"]
    R -->|no| TR["triage: claude -p, read-only tools,<br/>evidence fenced as untrusted,<br/>answer schema lists ONLY allowlisted actions"]
    TR -->|error or 15 min| TS["triage stopped (reported); the night goes on"]
    TR -->|transient + action| X["allowlist executor<br/>argv only, anchored params, once per item per night"]
    X -->|refused| RF["not fixed: the refusal named"]
    X -->|ran| V{"verified within 60 min?<br/>new CI run / Dagster run / retry Job / unit"}
    V -->|yes| FX["fixed by an allowlisted retry"]
    V -->|no| NF["not fixed: what verification saw"]
    TR -->|real + fix| FB["auto-fix/date-slug worktree<br/>edit-only agent, one local commit, never pushed"]
    FB --> G{"trusted checkout's local-gates.py<br/>+ Sonar pre-check in the tree"}
    G -->|pass| RD["fix branch ready"]
    G -->|fail| GF["not fixed: the gate's own last line"]
    TR -->|unknown / no safe action| PD["not fixed: a person decides"]
    NC & AG & RC & TS & RF & FX & NF & RD & GF & PD --> REP["report: Slack #alerts · comment on each Auto-Filed incident ·<br/>reports/date.md · history"]
    REP --> K["Kuma push 'morning-remediation' (25 h)<br/>no push = the run never happened = page"]
```

The safety lines, in order: triage can only read; the only actions are the four in `scripts/morning/allowlist.yaml`;
each runs once per item per night; nothing counts as fixed until verified; code changes stay on a local branch that the
trusted checkout's gates judged; the report never says more than was verified.
