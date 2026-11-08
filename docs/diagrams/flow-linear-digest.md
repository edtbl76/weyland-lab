# Flow — weekly Linear digest to Slack (B237)

Every Monday at 05:40 NY, twenty minutes after the nightly Linear snapshot (B194,
[flow-linear-backup.md](flow-linear-backup.md)), Dagster reads the newest complete snapshot from MinIO and posts one
summary of the Weyland Lab board to Slack `#linear-updates`. It never calls the Linear API, so it needs no Linear
credential. Operate: [runbooks/linear-backup.md](../runbooks/linear-backup.md) § Weekly digest.

```mermaid
sequenceDiagram
    participant S as Dagster schedule (Mon 05:40 NY)
    participant A as linear_weekly_digest asset
    participant M as MinIO linear-backup
    participant L as linear_digest leaf (dagster-free)
    participant K as Slack #linear-updates webhook
    S->>A: run linear_digest_job
    A->>M: newest snapshots/ts/ that has manifest.json
    M-->>A: manifest + issues, workflowStates, issueLabels, projects
    A->>L: check_fresh(manifest)
    alt finished_at missing or older than 26 h
        L-->>A: DigestError (stale snapshot)
        A-->>S: run FAILED, nothing posted
    else fresh
        A->>L: build_digest (Weyland Lab, last 7 days)
        L-->>A: closed, opened, High lane with holds, stale 30+ days
        A->>L: format_slack (max 10 lines a list, true counts, 3000-char sections)
        A->>K: POST the message
        alt HTTP 200 and body ok
            K-->>A: ok
            A-->>S: run succeeded, counts in run metadata
        else anything else
            K-->>A: error status or body
            A-->>S: run FAILED (the webhook URL never appears in the error)
        end
    end
    Note over S,K: dagster-freshness-check alerts on a FAILED run, or on no success within 8 days
```

- **Fails closed.** A stale snapshot, a missing webhook Secret, an unknown project or any reply but `200 ok` fails the
  run; the freshness watchdog turns that into an alert. Stale numbers are never posted as this week's.
- **Weyland Lab only.** Issues from other projects (Stud.IO, Weyland Auto-Filed) never reach the counts.
- **A quiet week still posts**, with zero counts, so silence never means "the digest broke".
