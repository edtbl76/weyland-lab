# Demo — SQLite app-store backups (Open WebUI + Woodpecker + Bifrost) and Woodpecker's lock fix (B182 / B201 / B202)

Two apps keep their whole state in one live SQLite file on mother, and neither had a backup: Open WebUI (users, chats,
settings, presets) and Woodpecker (users, repos, CI secrets, the nightly cron, pipeline history). One tested script,
`scripts/sqlite_backup.py`, backs both up every night and fails closed. Woodpecker's `database is locked` — which
killed an in-flight pipeline when the nightly cron fired — is fixed with a one-connection pool and watched by two Loki
alerts. **The restore drill and the recreated collision ARE the validation.** All RUN 2026-10-05/06. **Bifrost's**
`config.db` (providers, keys, budgets, MCP clients, prompts, skills) joined on 2026-10-08 (B202, before its v2
migration) — step 6.

## Sequence diagram
See [../diagrams/flow-sqlite-backup.md](../diagrams/flow-sqlite-backup.md).

## Prerequisites
`kubectl` on rogueone (pointed at mother), `woodpecker-cli` + creds in `scripts/.env`, Grafana/Telegram access.

## CLI walkthrough

**1. Run both backups now** (the nightly CronJobs, triggered by hand):
```
kubectl -n woodpecker create job --from=cronjob/woodpecker-backup woodpecker-backup-manual-$(date +%s) && kubectl -n weyland create job --from=cronjob/open-webui-backup open-webui-backup-manual-$(date +%s)
```
```
sqlite-backup OK (woodpecker.sqlite): /backup/woodpecker/20261006T025115Z — counts={'users': 1, 'pipelines': 284} files=['woodpecker.sqlite']
sqlite-backup OK (webui.db): /backup/open-webui/20261006T025112Z — counts={'user': 2, 'chat': 5} files=['uploads.tar.gz', 'vector_db.tar.gz', 'webui.db']
```
(Read with `kubectl -n <ns> logs job/<job-name>`.) Woodpecker's runs as uid 1000 — the server's own user.

**2. Restore drill (non-destructive)** — the commands are in runbooks/woodpecker.md § Backup + restore and
runbooks/open-webui.md § Restore drill. Woodpecker, RUN 2026-10-05:
```
backup 20261006T025115Z integrity ok manifest {'users': 1, 'pipelines': 284}
tables: ['agents', 'configs', 'crons', 'forges', 'log_entries', 'migration', 'orgs', 'perms', 'pipeline_configs', 'pipelines', 'redirections', 'registries', 'repos', 'secrets', 'server_configs', 'sqlite_sequence', 'steps', 'tasks', 'users', 'workflows']
```
Open WebUI, RUN 2026-10-04: `integrity ok users 2 chats 3 models 1`, the `agent-memory` connection present, both archives readable.

**3. Negative cases — it fails closed** (the real script in its image, against a scratch db; RUN 2026-10-06):

[rogueone]
```
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v /home/edwardmangini/IdeaProjects/weyland/scripts:/s:ro python:3.12-alpine sh -c 'mkdir -p /tmp/d /tmp/b && python3 -c "import sqlite3; c=sqlite3.connect(\"/tmp/d/woodpecker.sqlite\"); c.execute(\"create table users(id)\"); c.execute(\"create table pipelines(id)\"); c.commit()"; python3 /s/sqlite_backup.py --db woodpecker.sqlite --require users --require pipelines --keep 7 /tmp/d /tmp/b; echo "exit=$? backups-left=$(ls -A /tmp/b | wc -l)"; python3 /s/sqlite_backup.py --db woodpecker.sqlite --keep 7 /tmp/d /tmp/b; echo "exit=$?"'
```
```
sqlite-backup FAILED (woodpecker.sqlite): required table users is empty — the wrong or an empty database, not the app's state
exit=2 backups-left=0
sqlite-backup FAILED: no --require table — a check that checks nothing is not a backup
exit=2
```
In the cluster an exit 2 is a failed Job → `ScheduledBackupFailed` (critical); no success in 26h → `ScheduledJobStale`.

**4. The Woodpecker lock — the #252 collision recreated on demand** (instead of waiting for 01:00): start a lean run,
then fire the REAL `nightly-images` cron through the API 20 s later:
```
woodpecker-cli pipeline create edtbl76/weyland-lab --branch main --var RUN_FIXTURES=0
```
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && python3 -c "import json,os,urllib.request; s=os.environ['WOODPECKER_SERVER'].rstrip('/'); print(json.load(urllib.request.urlopen(urllib.request.Request(s+'/api/repos/2/cron/2',method='POST',headers={'Authorization':'Bearer '+os.environ['WOODPECKER_TOKEN']}),timeout=30))['number'])"
```
RUN 3× 2026-10-06 03:01–03:34Z: lean **#270 / #272 / #274 all `success`** while the cron runs #271 / #273 / #275
(event `cron`) ran 16–17 steps clean (each stopped after the lean run finished, so no full run landed in the 00:00–01:00
window). Server log: **0** `database is locked` / `task expired`. Before the fix the same overlap killed #252 in 20 s.

**6. Bifrost (B202) — run now, nightly, and the restore drill.** Run one now (also before any Bifrost upgrade):
```
kubectl -n weyland create job --from=cronjob/bifrost-backup bifrost-backup-manual-$(date +%s)
```
The first nightly run (23:55 NY, 2026-10-08 → `kubectl -n weyland logs job/bifrost-backup-29858635`):
```
sqlite-backup OK (config.db): /backup/bifrost/20261009T035501Z — counts={'config_providers': 22, 'governance_virtual_keys': 4, 'prompts': 280, 'skills': 589, 'config_mcp_clients': 10, 'prompt_versions': 287} files=['config.db']
```
Runs as uid 10001, Bifrost's own user. The non-destructive drill (command in runbooks/mcp-gateway.md § Bifrost backup +
restore — a detached pod opens a COPY of the newest backup), RUN 2026-10-08 on `20261008T200346Z`: `integrity ok`;
providers 22, virtual keys 4, MCP clients 10, prompts 280, skills 589 — every count matching the manifest. The
pre-upgrade backup `20261009T041944Z` (same counts) was the rollback point for the v2.2.6 migration.

**5. The alerts reach Telegram** — a labelled DRILL `WoodpeckerTaskExpired` (command in runbooks/woodpecker.md):
`alertmanager_notifications_total{integration="telegram"}` 13,476 → **13,477**, failed unchanged at 17.

## UI walkthrough (UAT — eyes on)
1. **Telegram** — the message *"DRILL — WoodpeckerTaskExpired (… nothing is wrong)"* arrived, then resolved ~2 min later.
2. **Grafana → Alerting → Alert rules** (data source Loki, group `weyland-log-alerts`): `WoodpeckerDatabaseLocked` and
   `WoodpeckerTaskExpired` listed, state **Normal**.
3. **Argo CD** (`https://argocd.weyland.lab`) → app **woodpecker-backup**: Synced + Healthy; CronJob `woodpecker-backup`
   schedule `50 23 * * *` America/New_York.
4. **Argo CD** → app **bifrost**: Synced + Healthy; CronJob `bifrost-backup` schedule `55 23 * * *` America/New_York,
   last run Complete.
5. **Woodpecker** (`https://woodpecker.weyland.lab`) → weyland-lab: #270/#272/#274 green; #271/#273/#275 (cron) killed by
   the operator — expected, they were only the collision.

## Expected result
- Each nightly backup leaves a timestamped directory with the db (+ archives) and a manifest; 7 kept; a backup that
  proves nothing exits 2 and pages critical.
- A pipeline in flight when the nightly cron fires is NOT killed; no `database is locked` in the server log.

## Cleanup / teardown
Manual backup Jobs clear themselves after 72h (`ttlSecondsAfterFinished`); the drill pods are `--rm`; the negative case
writes only inside a throwaway container. The three cron pipelines started for the collision were stopped by hand
(status `killed` in the UI is that, not a failure).
