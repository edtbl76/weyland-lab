# Demo — rogueone backup + restore (B130)

rogueone's encrypted restic backup to MinIO, and the restore that proves it. **The restore IS the validation** — a
backup you haven't restored isn't a backup. Validated live 2026-08-20: snapshot `d1e2bc7e` (652 MiB logical / 415M
deduped), restore of the mkcert CA + `.claude` memory + STUD.io `.env` diffed **byte-identical** against live.

## Sequence diagram
See [../diagrams/flow-backup.md](../diagrams/flow-backup.md).

## Prerequisites
- `restic` installed; MinIO bucket `rogueone-backup` (`mc mb weyland/rogueone-backup`); the 4 restic vars in
  `scripts/.env` (sourced by `nodes/rogueone/backup/.env`); `restic init` done.
- systemd user timer installed + `loginctl enable-linger` (see [../runbooks/backups.md](../runbooks/backups.md)).

## UI walkthrough (eyes-on UAT)
1. **Port** → Dashboards → **weyland Backups**. **UAT — confirm:** the status pie shows the latest run
   `success`; **Total Runs** ≥ 1; the runs table lists `rogueone-<ts>` with a repo size (~600–700 MiB) and a
   snapshot id. A run's `status` matches the script's exit.
2. **Uptime Kuma** (`kuma.weyland.lab`) → the **rogueone-backup** push monitor. **UAT — confirm:** it shows **Up**
   with a recent heartbeat (the last successful backup's ping), heartbeat interval ~26h, Telegram notification
   attached. (A silent >26h = it goes Down and pages Telegram — the dead-man's-switch.)

## CLI walkthrough
[rogueone] Run a backup now + confirm the snapshot:
```
set -a; . /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/backup/.env; set +a
/home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/backup/restic-backup.sh
restic snapshots
```
[rogueone] **Restore test** — restore the crown jewels to a scratch dir and diff against live:
```
restic restore latest --target /tmp/restore-test --include "$HOME/.local/share/mkcert" --include "$HOME/.claude/projects"
diff -rq "$HOME/.local/share/mkcert" /tmp/restore-test/"$HOME"/.local/share/mkcert && echo "RESTORE OK"
rm -rf /tmp/restore-test
```
[rogueone] Confirm the Port entity landed (client-creds from scripts/.env; secret never printed):
```
cd /home/edwardmangini/IdeaProjects/weyland; set -a; . ./scripts/.env; set +a; TOKEN=$(curl -sf -X POST https://api.getport.io/v1/auth/access_token -H "Content-Type: application/json" -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["accessToken"])'); curl -s "https://api.getport.io/v1/blueprints/backup/entities" -H "Authorization: Bearer $TOKEN" | python3 -c 'import sys,json;[print(e["identifier"],e["properties"]["status"]) for e in json.load(sys.stdin)["entities"]]'
```

## Expected result
- A `success` `backup` entity per run on the weyland Backups dashboard; the Kuma monitor Up with a fresh heartbeat.
- The restore reproduces the included paths byte-identical to live (`RESTORE OK`).

## Cleanup / teardown
- The restore writes only to `/tmp/restore-test` — removed by the last command.
- Each run creates one `backup` Port entity (kept — it's the history) and one restic snapshot (retention prunes to
  7d/4w/6m). A throwaway test entity is deletable via the Port API (`DELETE /v1/blueprints/backup/entities/<id>`).
