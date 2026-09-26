# Demo — Linear workspace backup (B194)

The nightly Linear snapshot, and the checks that prove it is a real backup rather than a green job. Sequence
diagram: [../diagrams/flow-linear-backup.md](../diagrams/flow-linear-backup.md). Runbook:
[../runbooks/linear-backup.md](../runbooks/linear-backup.md). DR row: [../dr.md](../dr.md).

**Status: PARTIAL.** Proven before deploy on 2026-09-26 (below). The live walkthrough runs after the new
`dagster-user-code` image ships; that run flips ledger row 84 to DONE.

## Proven before deploy (2026-09-26)

| Check | Result |
|---|---|
| Export against live Linear (read-only key) | 254 issues, 126 comments, 1,037 history events, 21 entity files; 70 API calls, ~16s, max page complexity 1,176 of 10,000 |
| Snapshot issue count vs an independent live count (archived included) | **254 = 254** |
| Materialize in the real `dagster-user-code` image against a throwaway MinIO | success; 22 objects, `manifest.json` written last; lifecycle rule `expire-snapshots` = 90 days on `snapshots/` |
| Negative: a revoked key | run fails with *"Linear rejected the read-only key — rotate linear-backup-secret"*; objects before/after 22/22 (nothing written) |
| Key is read-only | a mutation with it is refused `FORBIDDEN` |
| Unit tests (dagster-free leaf) | 16 passed |

## UI walkthrough (eyes-on UAT, after deploy)

1. **Dagster** (`dagster.weyland.lab`) → Overview → Schedules → `linear_backup_schedule`. **UAT — confirm:** it is
   **Running**, cron `20 5 * * *`, timezone America/New_York.
2. Jobs → `linear_backup_job` → **Launch run**. **UAT — confirm:** the run succeeds in well under a minute; the
   `linear_workspace_snapshot` materialization shows metadata `issues`, `comments`, `issue_history_events`,
   `bytes_written` and a `snapshot` path under `s3://linear-backup/snapshots/`.
3. **MinIO console / Filestash** → bucket `linear-backup` → the newest `snapshots/<ts>/`. **UAT — confirm:** 21
   `.json.gz` files plus `manifest.json`.
4. **Linear** → the team's issue list with archived included. **UAT — confirm:** the count matches the manifest's
   `issues`.

## CLI walkthrough (after deploy)

Run a backup now:

[mother]
```
kubectl exec -n weyland deploy/dagster-user-code -- dagster job execute -j linear_backup_job -m weyland_pipeline.definitions
```

Read the newest manifest:

[rogueone]
```
mc cat "weyland/linear-backup/snapshots/$(mc ls weyland/linear-backup/snapshots/ | tail -1 | awk '{print $NF}')manifest.json"
```

Confirm the retention rule and the NVMe mirror (the mirror appears after the next 22:30 `minio-backup` run):

[rogueone]
```
mc ilm rule ls weyland/linear-backup
```

[mother]
```
kubectl -n minio logs job/$(kubectl -n minio get jobs -o name | grep minio-backup | tail -1 | cut -d/ -f2) | grep linear-backup
```

## Cleanup

None. The demo writes one real snapshot, and that snapshot is the backup; the lifecycle rule expires it after 90
days like every other.
