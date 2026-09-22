# Flow: open-PR reconcile (B131 resolution half)

How `scripts/check-pr-lifecycle.sh` resolves open managed PRs. The three `pr-lifecycle/` watchdogs SURFACE
(alert, or reap a stale Port entity); this one RESOLVES. Runbook:
[runbooks/pr-lifecycle.md](../runbooks/pr-lifecycle.md) § "Resolving open PRs" · concept:
[concepts/linear-evaluation.md](../concepts/linear-evaluation.md).

```mermaid
flowchart TD
    OP[Operator<br/>check-pr-lifecycle.sh] --> LIST
    CRON[CronJob pr-lifecycle-reconcile<br/>03:25 NY, unmeshed, --apply] --> LIST[gh pr list open PRs]

    LIST --> MANAGED{Managed branch?<br/>dependabot or ci image-bump}
    MANAGED -->|no| IGNORE[Ignore<br/>human work]
    MANAGED -->|yes| SUP{Newer managed PR<br/>on same dir + package?}

    SUP -->|yes| SUPERSEDED[SUPERSEDED<br/>close, ref the newer]
    SUP -->|no| CLASS{dependabot?}

    CLASS -->|yes| CMP{compare.status<br/>diverged or behind?}
    CMP -->|error or empty| FC[FAIL CLOSED exit 2]
    CMP -->|yes| STALE[STALE<br/>dependabot recreate]
    CMP -->|no, CI green| MERGE1[MERGEABLE<br/>merge the bump]
    CMP -->|no, CI red| HUMAN1[NEEDS-HUMAN<br/>review]

    CLASS -->|no, image-bump survivor| SHIP{CI green?}
    SHIP -->|yes| MERGE2[MERGEABLE<br/>merge to ship]
    SHIP -->|no| HUMAN2[NEEDS-HUMAN<br/>review]

    STALE --> APPLY{--apply?}
    SUPERSEDED --> APPLY
    APPLY -->|yes| ACT[recreate stale<br/>close superseded<br/>NEVER merge]
    APPLY -->|no| REPORT[Advisory report<br/>exit 0]
    MERGE1 --> REPORT
    MERGE2 --> REPORT
    HUMAN1 --> REPORT
    HUMAN2 --> REPORT

    FC --> JOBFAIL[Failed Job<br/>ScheduledJobFailed to Telegram]
```

`STALE` never merges — a stale dependabot branch carries pre-remediation pins, so merging can silently
downgrade a hand-remediated CVE. `@dependabot recreate` re-cuts against current main and cannot regress.
Advisory by default; `--apply` performs only the low-risk resolutions (recreate, close) and **never merges**.
