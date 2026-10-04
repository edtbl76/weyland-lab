# Uptime Kuma — runbook (incident-management category, B43)

Uptime monitoring + status page at `kuma.weyland.lab`. **37 monitors** across the platform (live count, 2026-07-17). Two notifiers,
both default-on: **Port.io webhook** (→ `uptime_monitor` blueprint, catalog/status) and **direct Telegram**
(active paging — reuses the shared Telegram bot token (was Hermes's; the B66 operator inherits it); sending doesn't conflict with the operator consuming). Telegram is
the paging path on purpose — independent of any agent that could itself fail (see B45). Has its own built-in
auth (set on first login). Single container, SQLite state on a PVC.

- Manifest: `k8s/uptime-kuma/uptime-kuma.yaml` (PVC + Deployment + Service + Ingress, Traefik TLS).
- **UI access:** `kuma.weyland.lab` is now **Keycloak SSO gated via `traefik-forward-auth`** (forward-auth →
  Keycloak, in front of Kuma's own built-in login). The backup-script auth below is a separate API path, unaffected.
- Backup (monitors + notification): `scripts/kuma-backup.json` — **gitignored** (inline dev-password basic
  auth + the Port ingest key). Local-only.
- **Kuma's own login** (behind Keycloak): user `admin`, password = `LAB_PASSWORD` in `scripts/.env` (the lab dev
  password). Recorded 2026-10-03 after it was unknown when needed. The API is reachable for scripts via
  `kubectl -n weyland port-forward svc/uptime-kuma 13001:3001` (the UI hostname sits behind forward-auth); the
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

A **down** push is not the same as a missed one: `machine-inventory-drift` pushes `down` on purpose when it finds
host-software drift (it opens a `chore(inventory)` PR); it goes green again on the first clean night.

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
- 2nd notifier (default-on): Telegram, **reusing the Hermes bot token** + your chat ID. Sending is fine
  alongside Hermes (only *receiving*/getUpdates conflicts — which is why `getUpdates` returns nothing while
  Hermes owns the bot). Get your chat ID from **@userinfobot** (DM = your numeric user id), not getUpdates.

## Deploy (first time)
```
kubectl create secret generic weyland-mkcert-ca -n weyland --from-file=rootCA.pem=$(mkcert -CAROOT)/rootCA.pem
kubectl apply -f k8s/uptime-kuma/uptime-kuma.yaml && kubectl rollout status deploy/uptime-kuma -n weyland
```
Then `kuma.weyland.lab` → create admin → Settings → Backup → Restore → `scripts/kuma-backup.json`.
