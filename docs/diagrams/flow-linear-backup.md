# Flow — Linear workspace backup (B194)

The nightly snapshot of the Linear workspace into MinIO. The Dagster schedule fires at 05:20 NY and the asset builds
each entity's field selection from the live schema (one `__type` introspection per node type, because full-schema
introspection exceeds Linear's 10,000 complexity cap). It pages every entity with archived items included, finishes
any issue history longer than one nested page, validates, and only then writes. `manifest.json` goes last, so a
snapshot without one is incomplete by definition. Operate: [runbooks/linear-backup.md](../runbooks/linear-backup.md).
DR row: [dr.md](../dr.md).

```mermaid
sequenceDiagram
    participant S as Dagster schedule (05:20 NY)
    participant A as linear_workspace_snapshot (dagster-user-code)
    participant L as Linear GraphQL API
    participant M as MinIO linear-backup
    participant W as dagster-freshness-check (*/30)
    participant AM as Alertmanager to Telegram
    S->>A: run linear_backup_job
    A->>L: __type(name) per node type (read-only key)
    L-->>A: fields, used to build each selection
    loop each of 20 entities, 50 per page
        A->>L: root(first 50, after cursor, includeArchived true)
        L-->>A: nodes + pageInfo (any errors field fails the run, even on HTTP 200)
    end
    A->>L: issue(id).history for the issues with more than 50 events
    A->>L: templates
    A->>A: validate (required entities non-empty, history present)
    alt export complete
        A->>M: ensure bucket + 90-day lifecycle rule
        A->>M: put snapshots/ts/entity.json.gz x 21
        A->>M: put snapshots/ts/manifest.json (last, marks complete)
    else key rejected or export partial
        A-->>S: Failure, nothing written
    end
    W->>W: per-job check of the Dagster run DB
    alt last run failed, or no success in 30h
        W->>AM: DagsterJobFailed or DagsterJobStale (job linear_backup_job)
    end
```

The second copy is out of band: `minio-backup` (22:30) mirrors `linear-backup` to mother's NVMe with the other
irreplaceable buckets ([dr.md](../dr.md) § Blast radius).
