# Uptime Kuma — runbook (incident-management category, B43)

Uptime monitoring + status page at `kuma.weyland.lab`. **55 monitors** across the platform (live count, 2026-11-09; the
nightly `uptime-kuma-backup` log line carries the current one). Two notifiers,
both default-on: **Port.io webhook** (→ `uptime_monitor` blueprint, catalog/status) and **direct Telegram**
(active paging — a Telegram bot token, set up with Hermes's; which bot it is now is under Telegram paging below;
sending doesn't conflict with the operator consuming). Telegram is
the paging path on purpose — independent of any agent that could itself fail (see B45). Has its own built-in
auth (set on first login). Single container, SQLite state on a PVC.

- Manifest: `k8s/uptime-kuma/uptime-kuma.yaml` (PVC + Deployment + Service + Ingress, Traefik TLS).
- **UI access:** `kuma.weyland.lab` is now **Keycloak SSO gated via `traefik-forward-auth`** (forward-auth →
  Keycloak, in front of Kuma's own built-in login). The backup-script auth below is a separate API path, unaffected.
- Backup: the nightly `uptime-kuma-backup` CronJob (B240, 2026-11-09), § Backup + restore below. (The old local export
  `scripts/kuma-backup.json` named here before was gone when B240 looked, so until then nothing held a copy.)
- **Kuma's own login** (behind Keycloak): user `admin`, password = `LAB_PASSWORD` in `scripts/.env` (the lab dev
  password). Recorded 2026-10-03 after it was unknown when needed. The API is reachable for scripts via
  the `uptime-kuma-lan` NodePort `http://192.168.1.243:30301` (the UI hostname sits behind forward-auth); the
  `uptime-kuma-api` Python client logs in with those credentials.

## Push monitors — the heartbeat interval must outlast the job's cadence

A push monitor turns **down** when no push arrives within its heartbeat interval. Kuma's default is **60 s** — fine for
nothing that pushes on a timer. Set the interval to the job's cadence plus slack, or the monitor goes red a minute
after every successful push (found 2026-10-03: `machine-inventory-drift` and `agent-memory` were both left at 60 s).

| Push monitor | Pushed by | Cadence | Heartbeat interval | Env var (`scripts/.env`, no `?query`) |
|---|---|---|---|---|
| `rogueone-backup` | `restic-backup.timer` (rogueone) | daily 02:30 | **93600 s** (26 h) | `KUMA_BACKUP_PUSH_URL` |
| `machine-inventory-drift` | `machine-inv-drift.timer` (rogueone) | nightly ~03:45 | **93600 s** (26 h) — fixed from 60 s 2026-10-03 | `KUMA_INVENTORY_PUSH_URL` |
| `agent-memory` | `agent-memory-watch.timer` (rogueone, B182) | every 15 min | **1200 s** (20 min) — fixed from 60 s 2026-10-03 | `KUMA_MEMORY_PUSH_URL` |
| `emdash-conveyor` | `emdash-conveyor-watch.timer` (rogueone, B179) | daily 06:00 | **90000 s** (25 h) | `KUMA_CONVEYOR_PUSH_URL` |
| `lan-nodeports` | `lan-nodeport-watch.timer` (rogueone, B219) | every 15 min | **1200 s** (20 min) | `KUMA_LAN_PUSH_URL` |
| `gpu-driver-drift` | `gpu-driver-drift.timer` (rogueone, B226) | hourly | **4500 s** (75 min) | `KUMA_GPU_DRIFT_PUSH_URL` |

**This table is checked nightly** (2026-10-13): `machine-inv-drift.sh` runs `scripts/kuma_push_check.py`, which reads
every push monitor from Kuma's store (read-only) and turns `machine-inventory-drift` down on any interval that differs
from this table, a paused or missing monitor, or a push monitor with no row. **Add the row here BEFORE creating a push
monitor.** In Kuma's edit form the value goes in **Heartbeat Interval**, the first interval field. `emdash-conveyor` had
it in **Heartbeat Retry Interval**, leaving the heartbeat at 60 s, and the guard caught it on its first run. Check by
hand on rogueone:
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/kuma_push_check.py
```
Exit 0 all match · 1 findings, named · 2 could not read Kuma (never clean).

**Create a push monitor (step by step, Kuma 1.x).** Add its row to the table above FIRST, then:
1. Open `https://kuma.weyland.lab` (Keycloak SSO, then Kuma's own login: `admin` / `LAB_PASSWORD` from `scripts/.env`).
2. **+ Add New Monitor** (top left).
3. **Monitor Type:** `Push`. **Friendly Name:** the table's name (e.g. `lan-nodeports`).
4. **Heartbeat Interval:** the table's value (e.g. `1200`) — the FIRST interval field, not *Heartbeat Retry Interval*.
5. **Notifications** (right-hand column): tick the Telegram notification.
6. The form shows a **Push URL** (`https://kuma.weyland.lab/api/push/<token>?status=up&msg=OK&ping=`) with a copy
   button. Copy it and **delete everything from `?` on** — the watcher appends its own `?status=…`.
7. **Save**.
8. Put it in `scripts/.env` yourself as `<ENV VAR>=https://kuma.weyland.lab/api/push/<token>` (the table's env var).
   Never paste the URL into chat — the token is the credential.
9. Check: `python3 /home/edwardmangini/IdeaProjects/weyland/scripts/kuma_push_check.py` exits 0.

A **down** push is not the same as a missed one: `machine-inventory-drift` pushes `down` when the job or the estate
failed (an unreachable host, host placement drift, Port emit/verify, a push-interval finding). Catalog drift alone is
`up`, with the change and the open inventory PR in the message (since 2026-10-13).

## Backup + restore — `uptime-kuma-backup` (B240, 2026-11-09)

Kuma's whole state is ONE SQLite file, `kuma.db` (WAL mode, ~1.3 GB, mostly heartbeat history) on PVC
`uptime-kuma-pvc`: the 55 monitors, the 2 notifiers and their 78 links, the status page, the admin user. None of it is in
git. `k8s/uptime-kuma/uptime-kuma-backup.yaml` (deployed by the `uptime-kuma` Argo app) runs a CronJob at **23:58 NY**:
`scripts/sqlite_backup.py --db kuma.db --require monitor --require notification --require user` (the script shared with
the Open WebUI, Woodpecker and Bifrost backups, embedded by `scripts/embed-sqlite-backup.sh`), as root with every
capability dropped (Kuma runs as root and owns the file). It writes a consistent snapshot plus `manifest.json` to PVC
`uptime-kuma-backup` (mother NVMe) and keeps 7 (~9 GB). It fails closed → `ScheduledBackupFailed` (critical);
`ScheduledJobStale` after 26 h. **The copy holds the Telegram bot token and the Port webhook URL** (Kuma stores them in
its notification rows), the same boundary as the live PVC.

Run one now (and before any Kuma upgrade):
```
kubectl -n weyland create job --from=cronjob/uptime-kuma-backup uptime-kuma-backup-manual-$(date +%s)
```
Expect `sqlite-backup OK (kuma.db): /backup/uptime-kuma/<ts> — counts={'monitor': 55, 'notification': 2, 'user': 1,
'monitor_notification': 78, 'heartbeat': …} files=['kuma.db', 'manifest.json']`.

**Restore drill (non-destructive)** — opens the newest backup in a throwaway pod (copied to `/tmp`, never written back)
and prints integrity, the manifest counts and the same tables counted from the copy:
```
kubectl -n weyland run kuma-restore-drill --restart=Never --image=python:3.12-alpine --overrides='{"metadata":{"labels":{"sidecar.istio.io/inject":"false"}},"spec":{"automountServiceAccountToken":false,"containers":[{"name":"drill","image":"python:3.12-alpine","securityContext":{"runAsUser":0,"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]}},"command":["python3","-c","import glob,json,os,shutil,sqlite3; d=sorted(glob.glob(\"/backup/uptime-kuma/2*\"))[-1]; m=json.load(open(d+\"/manifest.json\")); shutil.copy(d+\"/kuma.db\",\"/tmp/r.db\"); c=sqlite3.connect(\"/tmp/r.db\"); q=lambda s: c.execute(s).fetchone()[0]; print(\"backup\",os.path.basename(d),\"integrity\",q(\"pragma integrity_check\"),\"manifest\",m[\"counts\"]); print(\"copy counts:\",{t:q(\"select count(*) from \"+t) for t in [\"monitor\",\"notification\",\"user\",\"monitor_notification\"]}); print(\"active monitors:\",q(\"select count(*) from monitor where active=1\"))"],"volumeMounts":[{"name":"b","mountPath":"/backup","readOnly":true}]}],"volumes":[{"name":"b","persistentVolumeClaim":{"claimName":"uptime-kuma-backup"}}]}}' >/dev/null && kubectl -n weyland wait --for=jsonpath='{.status.phase}'=Succeeded pod/kuma-restore-drill --timeout=300s >/dev/null; kubectl -n weyland logs kuma-restore-drill; kubectl -n weyland delete pod kuma-restore-drill
```
Pass = `integrity ok` and the counts matching the manifest and the live ones (read-only:
`kubectl -n weyland exec deploy/uptime-kuma -- sqlite3 -readonly /app/data/kuma.db "select count(*) from monitor"`).
Record the date in `docs/dr.md`.

**Restore (destructive).** Argo selfHeal reverts a scale-down, so pause the app first:
`argocd app set uptime-kuma --sync-policy none --grpc-web` → `kubectl -n weyland scale deploy/uptime-kuma --replicas=0` →
a one-off pod (root, no sidecar) mounting `uptime-kuma-pvc` (rw) and `uptime-kuma-backup` (ro) copies the chosen
`kuma.db` over `/app/data/kuma.db` and DELETES `kuma.db-wal` / `kuma.db-shm` → scale back to 1 → `argocd app set
uptime-kuma --sync-policy automated --self-heal --auto-prune --grpc-web`. Verify the monitor count in the UI and that a
test notification reaches Telegram.

## Gotchas (all hit during bring-up — don't repeat)
1. **DNS — `*.weyland.lab` is `ENOTFOUND` from the pod by default.** The pod must point at the LAN CoreDNS,
   not cluster DNS. The deployment sets `dnsPolicy: None` + `dnsConfig.nameservers: [192.168.1.243]` +
   `searches: [weyland.lab]`. Without this every `*.weyland.lab` monitor fails to resolve.
2. **TLS — self-signed mkcert CA.** Kuma (Node) rejects the `*.weyland.lab` certs unless it trusts the mkcert
   root. Mount it: secret `weyland-mkcert-ca` (from `$(mkcert -CAROOT)/rootCA.pem`) → `NODE_EXTRA_CA_CERTS`.
   Created out-of-band: `kubectl create secret generic weyland-mkcert-ca -n weyland --from-file=rootCA.pem=...`.
3. **Basic-auth monitors** (kiali, mlflow — Traefik `basicAuth` middleware): user `admin`, pass
   `weyland_dev_password`. **No trailing period** — the apr1 hash legitimately ends in `.`; do NOT copy the
   password from prose where it sits before a sentence-ending period. A stray `.` → silent 401.
4. **whisper** — `GET /inference` returns `404` (the route is POST-only); the server is still up, so accept
   status codes `200-299` + `400-499`.
5. ~~**hermes**~~ **RETIRED 2026-07-23** (CT-104 destroyed) — the B66 operator replaces it (a Telegram bot, outbound-only → not HTTP-monitored either).
6. **Restore is fragile.** Import "Overwrite" hits a **foreign-key-constraint bug** (heartbeat history);
   "Skip existing" silently skips updates to existing monitors. **Clean path: nuke the PVC and restore into an
   empty instance** — `kubectl delete deploy uptime-kuma -n weyland && kubectl delete pvc uptime-kuma-pvc -n
   weyland`, re-apply, re-create the admin, then restore `kuma-backup.json`. (Nuking the PVC also drops the
   notification — it comes back with the restore.)

## Port webhook
- Port Data Source (webhook) `uptime-kuma` → blueprint `uptime_monitor`. Mapping `operation` must be
  **`create`** (Port rejects `upsert`). URL: `https://ingest.getport.io/<webhookKey>`.
- In Kuma: Settings → Notifications → Webhook, content type `application/json`, set as **default** so new
  monitors auto-report. Kuma's default payload (`monitor.name`, `monitor.url`, `heartbeat.status`,
  `heartbeat.ping`) maps to the blueprint.

## Telegram paging
- 2nd notifier (default-on): Telegram, a bot token + your chat ID. It was set up with the Hermes bot's token
  (Hermes retired 2026-07-23); the B66 operator runs on a freshly minted bot ([operator.md](operator.md) § Bot mint),
  so check which token the notifier holds in Kuma (Settings → Notifications). Sending is fine alongside any
  receiver; only *receiving* (`getUpdates`) conflicts, and the operator pod owns receiving on its bot. Get your chat
  ID from **@userinfobot** (DM = your numeric user id), not `getUpdates`.

## Deploy (first time)
```
kubectl create secret generic weyland-mkcert-ca -n weyland --from-file=rootCA.pem=$(mkcert -CAROOT)/rootCA.pem
kubectl apply -f k8s/uptime-kuma/uptime-kuma.yaml && kubectl rollout status deploy/uptime-kuma -n weyland
```
Then `kuma.weyland.lab` → create admin → Settings → Backup → Restore → `scripts/kuma-backup.json`.
