# Runbook — Open WebUI (chat.weyland.lab)

Browser chat/voice UI on mother (`k8s/open-webui/`, Argo app `open-webui`, auto-sync + selfHeal). Backends: Ollama on
rogueone, the guarded `weyland-operator` lane (nemo-guardrails), whisper STT. Sign-in is Keycloak OIDC. Its state —
users, chats, settings, model presets (e.g. **Lab Recall**), tool-server connections (the shared agent memory) — is ONE
SQLite file, `webui.db` (WAL mode), on the RWO PVC `open-webui-data`. Catalogued in [../dr.md](../dr.md).

## Version — pinned

`deployment.yaml` pins the image by **digest** (it was `:main`, unpinned, until 2026-10-04). Change it only through the
upgrade procedure below: a new version migrates `webui.db` on start, and a downgrade is not supported.

## Backup — `open-webui-backup` (nightly 23:45 NY)

`k8s/open-webui/backup.yaml`: a CronJob runs `scripts/open_webui_backup.py` (embedded byte-identical by
`scripts/embed-open-webui-backup.sh`; tests `scripts/tests/test_open_webui_backup.py` + `open-webui-backup.bats`).
- **What:** a consistent snapshot of `webui.db` (SQLite online backup API — a file copy of a live WAL db is not one) +
  `vector_db.tar.gz` + `uploads.tar.gz` + `manifest.json` (written last: integrity, user/chat counts, files).
  `cache/` (~0.9 GB of re-downloadable model files) is skipped.
- **Where:** PVC `open-webui-backup` (local-path, mother **NVMe**), `/backup/open-webui/<UTC timestamp>/`; keeps **7**.
- **Fails closed** (exit 2 → failed Job): missing db, corrupt copy, or a copy with no users. Alerts (critical):
  `ScheduledBackupFailed` on a failed run, `ScheduledJobStale` after 26h with no success (`cron-freshness-rules.yaml`).

Run one now (before an upgrade, or to test):
```
kubectl -n weyland create job --from=cronjob/open-webui-backup open-webui-backup-manual-$(date +%s) && kubectl -n weyland wait --for=condition=complete --timeout=180s job -l app=open-webui-backup --field-selector status.successful=1 ; kubectl -n weyland logs -l app=open-webui-backup --tail=3
```
Expect `open-webui-backup OK: /backup/open-webui/<ts> — users=N chats=N tool_servers_configured=True files=[...]`.

## Restore drill (non-destructive — run after the first backup, and after any change to the backup)

Opens the newest backup READ-ONLY in a throwaway pod and proves it is a usable Open WebUI state: integrity, the users
and chats, the tool-server connection, the model presets. Nothing live is touched.
```
kubectl -n weyland run open-webui-restore-drill --rm -i --restart=Never --image=python:3.12-alpine --overrides='{"spec":{"automountServiceAccountToken":false,"containers":[{"name":"drill","image":"python:3.12-alpine","stdin":true,"command":["python3","-c","import glob,json,os,sqlite3,shutil,tarfile; d=sorted(x for x in glob.glob(\"/backup/open-webui/2*\"))[-1]; m=json.load(open(d+\"/manifest.json\")); shutil.copy(d+\"/webui.db\",\"/tmp/r.db\"); c=sqlite3.connect(\"/tmp/r.db\"); q=lambda s: c.execute(s).fetchone()[0]; print(\"backup\",os.path.basename(d),\"integrity\",q(\"pragma integrity_check\"),\"users\",q(\"select count(*) from user\"),\"chats\",q(\"select count(*) from chat\"),\"models\",q(\"select count(*) from model\"),\"agent-memory connection\",\"agent-memory\" in q(\"select value from config where key=\\u0027tool_server.connections\\u0027\")); [tarfile.open(d+\"/\"+t).getnames() for t in m[\"files\"] if t.endswith(\".tar.gz\")]; print(\"archives readable:\",[t for t in m[\"files\"] if t.endswith(\".tar.gz\")])"],"volumeMounts":[{"name":"b","mountPath":"/backup","readOnly":true}]}],"volumes":[{"name":"b","persistentVolumeClaim":{"claimName":"open-webui-backup"}}]}}'
```
Pass = `integrity ok`, the user/chat/model counts match the live app, `agent-memory connection True`,
and both archives open. Record the date in `docs/dr.md` (column "Last restore test").

## Restore (destructive — replaces the live state)

Argo selfHeal reverts a scale-down within ~3 min, so pause auto-sync first:
1. `argocd app set open-webui --sync-policy none --grpc-web`
2. `kubectl -n weyland scale deploy/open-webui --replicas=0 && kubectl -n weyland wait --for=delete pod -l app=open-webui --timeout=120s`
3. Copy the chosen backup over the data PVC with a one-off pod that mounts both (`open-webui-data` read-write,
   `open-webui-backup` read-only): copy `webui.db` to `/app/backend/data/webui.db`, **delete** `webui.db-wal` and
   `webui.db-shm` (they belong to the replaced file), and untar `vector_db.tar.gz` / `uploads.tar.gz` into the data dir.
4. `kubectl -n weyland scale deploy/open-webui --replicas=1`, then `argocd app set open-webui --sync-policy automated --self-heal --auto-prune --grpc-web`
5. Sign in; check chats, **Lab Recall**, and Admin → Settings → External Tools → `agent-memory`.

A restore must use a backup taken by the SAME or an OLDER version than the image that will run it (migrations only go
forward). The backup's version is the image that was running at its timestamp (`git log -- k8s/open-webui/deployment.yaml`).

## Upgrade

1. Run a backup now (above) and the restore drill — never upgrade without a verified copy from today.
2. Read the release notes between the running and target versions (`gh release view vX.Y.Z -R open-webui/open-webui`)
   for migrations and breaking changes.
3. Pin the target **release** digest in BOTH image lines of `deployment.yaml` (app + ca-bundle initContainer):
   `docker buildx imagetools inspect ghcr.io/open-webui/open-webui:vX.Y.Z` → the index `Digest:`.
4. Push; Argo rolls it (`Recreate`). Watch `kubectl -n weyland logs deploy/open-webui -c open-webui` for the migrations
   and `GET /api/version`. Then check sign-in, a chat, **Lab Recall**, and the `agent-memory` connection.
5. Rollback = revert the commit AND restore the pre-upgrade backup (the database has been migrated forward).

## Shared agent memory (MCP tool server)

The `agent-memory` connection (gateway `/mcp-memory`, `system_oauth` = each person's own Keycloak token) and the
**Lab Recall** preset: [shared-agent-memory.md](shared-agent-memory.md) § Open WebUI. Gotchas seen 2026-10-04: a
leading space pasted into the URL fails the connection with no request sent; Open WebUI's BUILT-IN tools (its own
`search_notes` for Notes, `search_knowledge_files`, `search_memories`) compete with ours — Lab Recall turns
**Builtin Tools** off; a custom model with no access grant is private and does not appear in the chat model picker.
