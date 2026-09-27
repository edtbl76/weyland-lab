# Demo — Linear workspace backup (B194)

The nightly Linear snapshot, and the checks that prove it is a real backup rather than a green job. Sequence
diagram: [../diagrams/flow-linear-backup.md](../diagrams/flow-linear-backup.md). Runbook:
[../runbooks/linear-backup.md](../runbooks/linear-backup.md). DR row: [../dr.md](../dr.md).

**Status: DONE (live, 2026-09-27).** Shipped in `dagster-user-code:git-473df840` (lean ship, pipeline #192) and
run live with the runbook's canonical command:

| Live check (2026-09-27 01:39 UTC) | Result |
|---|---|
| `dagster job execute -j linear_backup_job` in the pod | `RUN_SUCCESS`; 254 issues, 126 comments, 1,038 history events; 8.2s |
| Real bucket `linear-backup` | snapshot `2026-09-27T013914Z/`: 22 objects, `manifest.json` last |
| Manifest issue count vs an independent live count | **254 = 254** |
| Retention rule | `expire-snapshots` Enabled, prefix `snapshots/`, 90 days |
| Key in the pod | present, 48 chars (checked without printing it) |
| Watchdog sees the job | **pending** — the CLI run above used an ephemeral Dagster instance (no `DAGSTER_HOME` in the pod), so it never reached the run DB; the 02:00 UTC `dagster-freshness-check` did not list it. The first scheduled run (05:20 NY) is the proof; confirm `check linear_backup_job status=SUCCESS` in the next watchdog log |

## Restore drill (live, 2026-09-27)

`scripts/linear_restore.py --drill` against the 01:39 UTC snapshot:

| Check | Result |
|---|---|
| Issues restored into a scratch team | EMA-54 (parent) + EMA-13 (its sub-issue) + EMA-240; 23 comments incl. 5 threaded replies |
| Verification (title, description, priority, state, parent link, every comment in order) | **0 mismatches**, exit 0 |
| Reported as dropped | the retired team label `High`, cycle, project |
| Teardown | issues deleted, scratch team deleted; issue count back to 246, only team EMA remains |
| First drill (before the fixes) | failed usefully: SpecBot re-invoked by restored `@mentions` (43 comments read back vs 15) and a Linear escape (`*` → `\*`) — both fixed, both now tested |

Run it: see [../runbooks/linear-backup.md](../runbooks/linear-backup.md) § Restore.

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

Run a backup now (CLI — writes a real snapshot but is not recorded in Dagster's run DB; use the UI's **Launch run**
when the run must count for the watchdog):

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
