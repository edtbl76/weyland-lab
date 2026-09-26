# Linear backup runbook (B194)

A nightly snapshot of the whole Linear workspace (emangini) into MinIO, so the lab's status history, comments,
projects, initiatives, labels, templates and views survive a Linear outage, a bad bulk edit, or a lost account.
Catalogued in [../dr.md](../dr.md); timer in [../schedules.md](../schedules.md) (05:20 NY daily).

| | |
|---|---|
| What runs | Dagster asset `linear_workspace_snapshot` (group `linear_backup`), job `linear_backup_job`, schedule `linear_backup_schedule` |
| Code | `services/weyland-dagster/weyland_pipeline/assets/linear_backup.py` (transport, MinIO, asset) + `assets/datasets_lib/linear_export.py` (the export logic, dagster-free, tested in `tests/test_linear_export.py`) |
| Writes | `s3://linear-backup/snapshots/<UTC yyyy-mm-ddTHHMMSSZ>/<entity>.json.gz` × 21, then `manifest.json` **last** |
| Retention | 90 days — a MinIO lifecycle rule (`expire-snapshots`) the asset re-applies on every run |
| Second copy | `minio-backup` mirrors the bucket to mother's NVMe nightly (22:30) |
| Key | `LINEAR_API_KEY_RO` — **read-only** (Linear refuses mutations with it: `FORBIDDEN`), Secret `weyland/linear-backup-secret`, sealed |
| Alerts | `dagster-freshness-check` (every 30m): last run FAILED, or no success within 30h |

## What a snapshot holds

One gzipped JSON array per entity, every node with all its argument-free scalar fields and `{ id }` references to
related objects (built from the live schema each run, so new Linear fields are picked up without a code change):

issues (archived included, each with its full `history` — the state/assignee/label/priority change log) · comments ·
issueRelations · attachments · projects · projectUpdates · projectMilestones · projectStatuses · initiatives ·
initiativeUpdates · initiativeToProjects · issueLabels · projectLabels · initiativeLabels · customViews · cycles ·
documents · teams · users · workflowStates · templates.

`manifest.json` records the counts per entity (plus `issueHistory`), start/finish time and `format_version`.
**A snapshot directory without `manifest.json` is incomplete** — a run that died mid-write. Never restore from one.

**Not captured:** file uploads behind attachment URLs, notification/inbox state, integrations' own settings, and the
API keys themselves. Recorded so a restore doesn't assume them.

## Operate

Run a backup now (in the user-code pod, recorded under the job name so the watchdog sees it):

[mother]
```
kubectl exec -n weyland deploy/dagster-user-code -- dagster job execute -j linear_backup_job -m weyland_pipeline.definitions
```

List snapshots and read the newest manifest (from rogueone, `mc` alias `weyland` per [storage-minio.md](storage-minio.md)):

[rogueone]
```
mc ls weyland/linear-backup/snapshots/ | tail -5
```

[rogueone]
```
mc cat "weyland/linear-backup/snapshots/$(mc ls weyland/linear-backup/snapshots/ | tail -1 | awk '{print $NF}')manifest.json"
```

Check the retention rule:

[rogueone]
```
mc ilm rule ls weyland/linear-backup
```

## Verify a snapshot is complete (the acceptance check)

The manifest's issue count must equal a live count taken at the same time (archived included). The export itself
refuses to write when a required entity (issues, comments, projects, initiatives, labels, templates, views, states,
teams, users) comes back empty or when issue history is missing, so an empty-looking backup can't be published.

## Install / first-time setup

1. The key already exists in `scripts/.env` as `LINEAR_API_KEY_RO` (also the CI secret `linear_api_key`). Create
   the Secret from it without printing it:

   [rogueone]
   ```
   set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && kubectl -n weyland create secret generic linear-backup-secret --from-literal=LINEAR_API_KEY_RO="$LINEAR_API_KEY_RO" --dry-run=client -o yaml | kubectl -n weyland apply -f -
   ```
2. Verify the STORED value, not `DATA 1` — the length must be 48 (the key's length in `scripts/.env`):

   [rogueone]
   ```
   kubectl -n weyland get secret linear-backup-secret -o jsonpath='{.data.LINEAR_API_KEY_RO}' | base64 -d | wc -c
   ```
3. Seal just this one secret into the repo (it is in the `seal-secrets.sh` allow-list), per
   [secrets.md](secrets.md) § Rotate / re-seal:

   [rogueone]
   ```
   kubectl -n weyland annotate secret linear-backup-secret sealedsecrets.bitnami.com/managed=true --overwrite && kubectl -n weyland get secret linear-backup-secret -o yaml | kubeseal --format yaml > /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/sealed-secrets/sealed/weyland__linear-backup-secret.yaml
   ```
4. Commit + push (owner), let Argo sync, ship the new `dagster-user-code` image with `scripts/ship-images.sh`, then
   run a backup now (above) and confirm the manifest.

## Rotate the key

Create a new read-only key in Linear (Settings → Security & access → API keys, Read only), put it in
`scripts/.env` as `LINEAR_API_KEY_RO`, then repeat install steps 1–4 and revoke the old key in Linear. A revoked key
makes the next run fail with *"Linear rejected the read-only key — rotate linear-backup-secret"* and write nothing.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Run fails: *rejected the read-only key* | key revoked/expired, or the Secret is empty | rotate (above); check the stored length |
| Run fails: *required entities came back empty: …* | the key lost access to part of the workspace, or Linear changed an API | check the key's scope in Linear; re-run the export locally (below) |
| Run fails: *cursor did not advance* | Linear pagination bug or API change | re-run; if it repeats, capture the response and fix `linear_export.paginate` |
| Snapshot dir with no `manifest.json` | pod died mid-write | ignore it (incomplete by definition); the next run writes a fresh one |

Reproduce the export locally (read-only; writes nothing) — the leaf module runs with only the stdlib:

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-dagster && docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -e HOME=/tmp -v "$PWD":/w:ro -w /w python:3.12-slim sh -c "pip install -q --user pytest >/dev/null 2>&1; python -m pytest -q -p no:cacheprovider tests/test_linear_export.py"
```

## Restore

Not yet drilled — the restore drill (recreate sample issues + comments in a scratch team from a snapshot, and
document what Linear's API cannot restore: original ids, authorship, timestamps) is **B194 Slice 2**. Until it runs,
[../dr.md](../dr.md) lists Linear's last restore test as **never**.
