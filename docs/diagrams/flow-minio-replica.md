# Flow: MinIO replica on timberback — nightly copy, verify, and the dump files (B134)

How the lab's first backup on a second machine runs. Two CronJobs fill a versioned MinIO on timberback from the
primary on mother's USB disk. **`minio-replica-sync`** (00:25 NY, on timberback) mirrors every bucket and then checks
the result with `mc diff`. An object the replica lacks fails the run only if it predates the sync; writes that land
during the copy are counted and picked up the next night. **`minio-replica-pgdumps`** (00:30 NY, on mother) copies the
core Postgres dump files, which MinIO does not list, into the replica's `pg-dumps` bucket and checks each size.
Versioning plus a 30-day rule for old versions makes a bad delete or overwrite upstream recoverable for 30 days.
Design: [arch.md §10l](../arch.md). Runbook: [storage-minio.md § Replica](../runbooks/storage-minio.md).

```mermaid
sequenceDiagram
    participant C as CronJob minio-replica-sync (timberback, 00:25 NY)
    participant P as MinIO primary (mother, USB disk)
    participant R as MinIO replica (timberback NVMe, versioned)
    participant D as CronJob minio-replica-pgdumps (mother, 00:30 NY)
    participant H as host path /mnt/minio/backups/pg (mother)
    participant A as Prometheus alerts (Telegram)
    C->>P: mc ls (the bucket list, empty means fail)
    loop every bucket
        C->>R: mc mb + version enable + ilm import (30-day noncurrent rule)
        C->>P: mc mirror --overwrite --remove --retry
        P-->>R: new and changed objects (removed ones become old versions)
        C->>P: mc diff primary vs replica
        C->>C: classify each difference by its source lastModified
        alt object missing and older than the sync start
            C->>C: count as missing (fails the run)
        else written during the sync
            C->>C: count as late (next night copies it)
        end
    end
    C-->>A: job fails if missing above 0 or no buckets
    D->>H: list weyland-all-*.sql.gz (skip .partial)
    D->>R: mc mirror into pg-dumps
    D->>R: mc stat each dump and compare its size
    D-->>A: job fails on no dumps or a size mismatch
    Note over A: cron-freshness-rules.yaml - stale success or a failed job pages
    Note over R: restore = read from the replica (a current object, or an old version within 30 days)
```

Last proven 2026-11-17: the first full copy verified 22 buckets with 0 missing; the restore drill read a dump back
byte-identical, an old version of a deleted Loki object, and an MLflow artifact
([demos/backup-restore.md § MinIO replica](../demos/backup-restore.md)).
