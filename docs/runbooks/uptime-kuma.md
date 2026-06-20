# Uptime Kuma — runbook (incident-management category, B43)

Uptime monitoring + status page at `kuma.weyland.lab`. **16 monitors** across the platform. Two notifiers,
both default-on: **Port.io webhook** (→ `uptime_monitor` blueprint, catalog/status) and **direct Telegram**
(active paging — reuses the Hermes bot token; sending doesn't conflict with Hermes consuming). Telegram is
the paging path on purpose — independent of any agent that could itself fail (see B45). Has its own built-in
auth (set on first login). Single container, SQLite state on a PVC.

- Manifest: `k8s/uptime-kuma/uptime-kuma.yaml` (PVC + Deployment + Service + Ingress, Traefik TLS).
- Backup (monitors + notification): `scripts/kuma-backup.json` — **gitignored** (inline dev-password basic
  auth + the Port ingest key). Local-only.

## Gotchas (all hit during bring-up — don't repeat)
1. **DNS — `*.weyland.lab` is `ENOTFOUND` from the pod by default.** The pod must point at the LAN CoreDNS,
   not cluster DNS. The deployment sets `dnsPolicy: None` + `dnsConfig.nameservers: [192.168.1.243]` +
   `searches: [weyland.lab]`. Without this every `*.weyland.lab` monitor fails to resolve.
2. **TLS — self-signed mkcert CA.** Kuma (Node) rejects the `*.weyland.lab` certs unless it trusts the mkcert
   root. Mount it: secret `weyland-mkcert-ca` (from `$(mkcert -CAROOT)/rootCA.pem`) → `NODE_EXTRA_CA_CERTS`.
   Created out-of-band: `kubectl create secret generic weyland-mkcert-ca -n weyland --from-file=rootCA.pem=...`.
3. **Basic-auth monitors** (kiali, jaeger, mlflow — Traefik `basicAuth` middleware): user `admin`, pass
   `weyland_dev_password`. **No trailing period** — the apr1 hash legitimately ends in `.`; do NOT copy the
   password from prose where it sits before a sentence-ending period. A stray `.` → silent 401.
4. **whisper** — `GET /inference` returns `404` (the route is POST-only); the server is still up, so accept
   status codes `200-299` + `400-499`.
5. **hermes** — no HTTP/TCP endpoint reachable from the cluster (Telegram bot, outbound-only). Not monitored.
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
