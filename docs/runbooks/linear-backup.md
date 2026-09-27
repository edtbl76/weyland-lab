# Linear backup runbook (B194)

A nightly snapshot of the whole Linear workspace (emangini) into MinIO, so the lab's status history, comments,
projects, initiatives, labels, templates and views survive a Linear outage, a bad bulk edit, or a lost account.
Catalogued in [../dr.md](../dr.md); timer in [../schedules.md](../schedules.md) (05:20 NY daily).

| | |
|---|---|
| What runs | Dagster assets `linear_workspace_snapshot` → `linear_lakehouse_tables` (group `linear_backup`), job `linear_backup_job`, schedule `linear_backup_schedule` |
| Code | `services/weyland-dagster/weyland_pipeline/assets/linear_backup.py` (transport, MinIO, asset) + `assets/datasets_lib/linear_export.py` (the export logic, dagster-free, tested in `tests/test_linear_export.py`) |
| Writes | `s3://linear-backup/snapshots/<UTC yyyy-mm-ddTHHMMSSZ>/<entity>.json.gz` × 21, then `manifest.json` **last** |
| Retention | 90 days — a MinIO lifecycle rule (`expire-snapshots`) the asset re-applies on every run |
| Second copy | `minio-backup` mirrors the bucket to mother's NVMe nightly (22:30) |
| Key | `LINEAR_API_KEY_RO` — **read-only** (Linear refuses mutations with it: `FORBIDDEN`), Secret `weyland/linear-backup-secret`, sealed |
| Alerts | `dagster-freshness-check` (every 30m): last run FAILED, or no success within 30h |

## Lakehouse view (Slice 3)

After each snapshot the same job runs `linear_lakehouse_tables`, which flattens the newest snapshot that has a
manifest into Iceberg `linear.*` (Nessie `main`, via Trino `iceberg.linear.*`): `issues`, `issue_state_changes`,
`workflow_states`, `issue_labels`, `projects`, `initiatives`, `initiative_projects`, `initiative_updates`,
`project_updates`. Every table is overwritten each run (current state; the raw snapshots keep the history) with an
explicit schema; a changed schema drops and recreates the table (the tables are derived). An empty `issues` fails the
run. The dbt marts on top — `mart_linear_issue_cycle_time` (B185), `mart_linear_weekly_flow` (EMA-172),
`mart_linear_initiative_progress` (B119.1) — build with the weekly `weyland_dbt_job`; queries in
[../query/dbt-marts.md](../query/dbt-marts.md) § Linear. Build just those three now (recorded, via the Dagster API):

[mother]
```
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import json,urllib.request;q='mutation(\$p:ExecutionParams!){launchRun(executionParams:\$p){__typename ... on LaunchRunSuccess{run{runId}} ... on PythonError{message}}}';v={'p':{'selector':{'repositoryLocationName':'weyland_pipeline','repositoryName':'__repository__','jobName':'weyland_dbt_job','assetSelection':[{'path':[m]} for m in ['mart_linear_issue_cycle_time','mart_linear_weekly_flow','mart_linear_initiative_progress']]},'runConfigData':{}}};r=urllib.request.Request('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql',data=json.dumps({'query':q,'variables':v}).encode(),headers={'Content-Type':'application/json'});print(json.load(urllib.request.urlopen(r))['data']['launchRun'])"
```

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

Run a backup now, **recorded** (the canonical command — it is exactly what the UI's **Launch run** does: the run goes
through the daemon into Dagster's run database, so `dagster-freshness-check` sees it and its 30h budget resets):

[mother]
```
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import json,urllib.request;q='mutation(\$p:ExecutionParams!){launchRun(executionParams:\$p){__typename ... on LaunchRunSuccess{run{runId status}} ... on PythonError{message}}}';v={'p':{'selector':{'repositoryLocationName':'weyland_pipeline','repositoryName':'__repository__','jobName':'linear_backup_job'},'runConfigData':{}}};r=urllib.request.Request('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql',data=json.dumps({'query':q,'variables':v}).encode(),headers={'Content-Type':'application/json'});print(json.load(urllib.request.urlopen(r))['data']['launchRun'])"
```

Then run the watchdog once instead of waiting for its next tick, read its line for the job, and remove the ad-hoc Job:

[mother]
```
kubectl -n weyland create job dagster-freshness-check-now --from=cronjob/dagster-freshness-check && kubectl -n weyland wait --for=condition=complete job/dagster-freshness-check-now --timeout=150s && kubectl -n weyland logs job/dagster-freshness-check-now -c check | grep linear_backup_job; kubectl -n weyland delete job dagster-freshness-check-now
```

**CLI (writes a real snapshot, NOT recorded):** the user-code pod has no `DAGSTER_HOME`, so `dagster job execute`
runs on an ephemeral in-memory instance. The snapshot lands in MinIO like any other, but the run never reaches the
run database — the watchdog cannot see it, and it does not reset the 30h budget (found 2026-09-27: a CLI run at
01:39 UTC was absent from the 02:00 watchdog check). Use it to test the export, not to satisfy the alert:

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

`scripts/linear_restore.py` (tests: `scripts/tests/test_linear_restore.py`) rebuilds issues + comments from a
snapshot with the **write** key (`LINEAR_API_KEY` in `scripts/.env`). Download the snapshot first (a directory without
`manifest.json` is refused as incomplete):

[rogueone]
```
mkdir -p /home/edwardmangini/linear-restore && mc cp -r "weyland/linear-backup/snapshots/$(mc ls weyland/linear-backup/snapshots/ | tail -1 | awk '{print $NF}')" /home/edwardmangini/linear-restore/
```

**The drill** (scratch team → restore → read back + verify every field → delete the issues and the team, always):

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && set -a && . scripts/.env && set +a && python3 scripts/linear_restore.py --snapshot /home/edwardmangini/linear-restore/<ts> --issues EMA-54,EMA-13,EMA-240 --drill
```

**A real restore** into an existing team (kept): replace `--drill` with `--team-id <team uuid>`. Exit 0 = restored and
verified; 1 = a mismatch or teardown failure; 2 = could not run.

| Restored | Not restorable (carried in a provenance header) | Dropped, reported per issue |
|---|---|---|
| title, description, priority, state (by name, else type), workspace labels, due date, parent links (when the parent is restored too), comments with reply threading | original identifier (EMA-n is reissued), creator and comment authors (everything is created by the key's user), created/updated timestamps, the history log, reactions | team-scoped labels, cycle, project, milestone, assignee, estimate |

**Limits found by the drill (2026-09-27):**
- **SpecBot auto-reviews every new issue** — each restored issue spends one of its capped monthly analyses. Restored
  text has its `@mentions` neutralized (an invisible word joiner), otherwise every `@SpecBot` in an old comment
  re-invokes the agent (the first drill read back 43 comments on an issue restored with 15).
- **Linear re-renders markdown** (`*` → `\*`, `-` bullets → `*`); verification compares meaning, not bytes.
- **The Free plan stops issue creation above 250 issues.** The workspace sits at ~246, so a full-workspace restore on
  Free is impossible: restore selectively, or archive first, or upgrade for the duration of a disaster recovery.
- Comments written by bots are ignored when verifying (they are not part of what was restored).

**Last drill: 2026-09-27** — EMA-54 + its sub-issue EMA-13 + EMA-240 (15 comments, 5 threaded replies): 3 issues,
23 comments, parent link and every field verified, torn down (issue count back to 246, only team EMA remains).
