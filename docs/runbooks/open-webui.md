# Runbook — Open WebUI (chat.weyland.lab)

Browser chat/voice UI on mother (`k8s/open-webui/`, Argo app `open-webui`, auto-sync + selfHeal). Backends: Ollama on
rogueone, the guarded `weyland-operator` lane (nemo-guardrails), whisper STT. Sign-in is Keycloak OIDC. Its state —
users, chats, settings, model presets (e.g. **Lab Recall**), tool-server connections (the shared agent memory) — is ONE
SQLite file, `webui.db` (WAL mode), on the RWO PVC `open-webui-data`. Catalogued in [../dr.md](../dr.md).

## Version — pinned

`deployment.yaml` pins the image by **digest** (it was `:main`, unpinned, until 2026-10-04). Change it only through the
upgrade procedure below: a new version migrates `webui.db` on start, and a downgrade is not supported.

## Backup — `open-webui-backup` (nightly 23:45 NY)

`k8s/open-webui/backup.yaml`: a CronJob runs `scripts/sqlite_backup.py --db webui.db --require user --count chat
--archive vector_db --archive uploads` — the SQLite backup script shared with `woodpecker-backup` (embedded byte-identical
by `scripts/embed-sqlite-backup.sh`; tests `scripts/tests/test_sqlite_backup.py` + `sqlite-backup.bats`).
- **What:** a consistent snapshot of `webui.db` (SQLite online backup API — a file copy of a live WAL db is not one) +
  `vector_db.tar.gz` + `uploads.tar.gz` + `manifest.json` (written last: integrity, user/chat counts, files).
  `cache/` (~0.9 GB of re-downloadable model files) is skipped.
- **Where:** PVC `open-webui-backup` (local-path, mother **NVMe**), `/backup/open-webui/<UTC timestamp>/`; keeps **7**.
- **Fails closed** (exit 2 → failed Job): missing db, corrupt copy, or a copy with no users. Alerts (critical):
  `ScheduledBackupFailed` on a failed run, `ScheduledJobStale` after 26h with no success (`cron-freshness-rules.yaml`).

Run one now (before an upgrade, or to test):
```
J=open-webui-backup-manual-$(date +%s) && kubectl -n weyland create job --from=cronjob/open-webui-backup $J && kubectl -n weyland wait --for=condition=complete --timeout=180s job/$J && kubectl -n weyland logs job/$J --tail=3
```
Expect `sqlite-backup OK (webui.db): /backup/open-webui/<ts> — counts={'user': N, 'chat': N} files=[...]` with **today's**
timestamp. It waits on the job it created, by name: until 2026-11-12 this command waited on `-l app=open-webui-backup
--field-selector status.successful=1`, which matched the nightly jobs that had already completed, returned at once and
printed THEIR logs while the new job was still starting — a success report for a backup not yet taken.

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

## Login lifetime — 10h, with Keycloak (2026-10-05)

Admin Panel → Settings → **Authentication** → **JWT Expiration = `10h`** (0.11.x moved it there from General) (stored in the DB as `auth.jwt_expiry`; it was `4w`), matching
the Keycloak realm's 10h session (runbooks/keycloak.md § Session lifetime). With a longer Open WebUI login, the first
tool call after the Keycloak session lapsed went out with no token (`mcp-gateway-audit … user=- status=401`).

## Shared agent memory (MCP tool server)

The `agent-memory` connection (gateway `/mcp-memory`, `system_oauth` = each person's own Keycloak token) and the
**Lab Recall** preset: [shared-agent-memory.md](shared-agent-memory.md) § Open WebUI. Gotchas seen 2026-10-04: a
leading space pasted into the URL fails the connection with no request sent; Open WebUI's BUILT-IN tools (its own
`search_notes` for Notes, `search_knowledge_files`, `search_memories`) compete with ours — Lab Recall turns
**Builtin Tools** off; a custom model with no access grant is private and does not appear in the chat model picker.

## Curated workspace (B116, 2026-11-12)

The workspace settings live in `webui.db`, not in git, so a restore from an older backup or a rebuilt data volume loses
them without a word. **`scripts/open_webui_curate.py` is their one definition.** Check for drift (read only; exit 1 on
any drift) — run it after every restore and every upgrade:

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && set -a && . scripts/.env && set +a && python3 scripts/open_webui_curate.py --check
```

Apply the curated state (the same command without `--check`; it applies, then runs the same check). It needs
`OPEN_WEBUI_API_KEY` in `scripts/.env`: an admin's key, created in **Settings → Account → API keys → API Key**, which
appears once **Admin Panel → Settings → Authentication → API Keys** is on (0.12 layout).

| Setting | Curated value | Why |
|---|---|---|
| OpenAI-style connections | only `nemo-guardrails` (the guarded `weyland-operator` lane) | an enabled `api.openai.com` connection with no key had been left in the database: outbound, and the lab is LAN-only and $0 |
| Community sharing · Arena model | off · off | sharing would publish chats to openwebui.com; Arena added a noise entry to the picker |
| Hidden models | `nomic-embed-text`, `gpt-oss:20b-judge`, `qwen2.5:7b-operator`, `qwen3-coder:30b-32k` | an embedder, the eval judge, the operator's own variant, a duplicate — not chat models |
| Default model · order | **Lab Recall** · `weyland-operator`, Lab Recall, **Lab Status**, then the chat models | |
| Default context | `num_ctx` **16384** | Ollama's 4096 default cut every chat with tools selected to ~2,050 tokens (Ollama halves an overflowing prompt), so the model saw only part of its tool list and answered "I have no such tools" |
| Lab Recall | web search, image generation, terminal **off** | nothing is configured behind those buttons |
| Tool servers | `agent-memory` → `/mcp-memory`; **`lab-fleet` → `/mcp-fleet`**, 13 read-only tools | both `system_oauth`: the signed-in person's own Keycloak token, so the MCP gateway audits every call as them (`path=/mcp-fleet actor=open-webui user=<you>`) |
| **Lab Status** preset | `qwen3:30b-a3b` + `lab-fleet` on by default, builtin tools off, a read-only system prompt that knows where alerts live | live lab status from chat; answered "only Watchdog is firing" in ~12 s (2026-11-12) |

**Gotchas found doing it (0.12.5):**
- An API key **cannot send MFA fields**: a `POST /api/v1/auths/admin/config` carrying `ENABLE_MFA` or `MFA_*` gets 403
  ("A human administrator session is required"), even unchanged. The server applies only the MFA fields a request
  sends, so leave them out.
- Hidden base models are workspace-model entries with `meta.hidden: true`, listed by **`/api/v1/models/all`**;
  `/api/v1/models/list` returns presets only.
- A tool server's **`function_name_filter_list` matches by suffix** (`endswith`), so a prefix such as `memory_` filters
  nothing: list the full tool names to allow.
- **Grafana OnCall is not run here**: the fleet's `grafana_list_alert_groups` answers 404. Firing alerts are
  `ALERTS{alertstate="firing"}` in Prometheus (datasource uid `prometheus`); `Watchdog` always fires by design.
- `qwen3:30b-a3b` on rogueone is the **Thinking-2507** build (262k context): it always reasons. `think: false` (and
  `/no_think`) only stop Ollama separating the reasoning, which then spills into the answer as raw text — leave
  thinking on and Open WebUI folds it away.
- The **first account** (`me@emangini.com`, the primary admin) cannot be deleted or demoted through the API or the UI;
  it stays as the break-glass admin (the password login form is on for when Keycloak is down).
- A chat request sent with an **API key** does not behave like a browser chat (a preset's tools and prompt were not
  applied, and it never returned): test chat behaviour in the browser.
- The browser loads the tool-server list once per page: **reload** after adding a connection.

**Text-to-speech is not configured** (speech-to-text is whisper): a local TTS engine is deferred until the new hardware
is in service — **B246**.
