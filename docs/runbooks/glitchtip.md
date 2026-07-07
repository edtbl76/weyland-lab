# B51 — GlitchTip Runbook — weyland (error tracking)

Self-hosted, Sentry-SDK-compatible error tracking. Replaces the "self-hosted Sentry" idea (which is ~20-40
containers) with GlitchTip's lean stack. Lives in the `weyland` k8s namespace; UI at `glitchtip.weyland.lab`.
Roadmap: B51. Apps push errors via the Sentry SDK; issues fan out to Port via a webhook.

---

## What it is

**GlitchTip 6.2** (Django + granian). Three workloads + the shared meshed Postgres:
- **glitchtip-web** — the UI + the Sentry **ingest API** (granian, `:8000`). Meshed (Istio sidecar).
- **glitchtip-worker** — Celery + beat (`./bin/run-celery-with-beat.sh`); processes ingested events into
  issues, runs alert/uptime tasks. Without it, events ingest but **never become visible issues**.
- **glitchtip-valkey** — `valkey/valkey:8-alpine` (`glitchtip-valkey:6379`). Django cache **and** the Celery
  broker. **Not optional** (see gotchas).
- **Postgres** — the shared `weyland-postgres` (STRICT mTLS) → the web/worker pods must be **meshed**.

Manifests: `k8s/glitchtip/glitchtip.yaml` (raw, single file). Deploy = rsync to mother → `kubectl apply` →
`kubectl rollout restart deploy/glitchtip-web -n weyland` (and `-worker`).

## Bring-up gotchas (hard-won — don't re-derive)

1. **Does NOT auto-migrate.** A fresh DB → `relation "users_user" does not exist` on first login. The manifest
   runs migrations in an **initContainer** (`./manage.py migrate`). If you ever see missing-table errors, the
   migrate step didn't run.
2. **Valkey is REQUIRED for the cache** (`django_vcache`). Without it, login/register 500 with
   `ConnectionError: Name or service not known`. **And the URL scheme matters:** `VALKEY_URL=valkey://…` —
   **NOT** `redis://…` (GlitchTip 6.2 mis-parses `redis://` as a literal hostname). `REDIS_URL` stays
   `redis://glitchtip-valkey:6379/0` (Celery broker); `VALKEY_URL` is the `valkey://` one.
3. **`ALLOWED_HOSTS=*`.** The k8s readiness probe hits the **pod IP**, not the hostname → Django 400s with
   `DisallowedHost` and the pod never goes Ready if ALLOWED_HOSTS is pinned to `glitchtip.weyland.lab`. Set `*`
   (LAN-only service, behind the mesh + Traefik).
4. **No registration link / register 500** on a fresh instance → create the admin from the CLI:
   `kubectl exec -n weyland deploy/glitchtip-web -c glitchtip -- ./manage.py createsuperuser`. After that,
   **`ENABLE_USER_REGISTRATION=false`** (locked; open registration 500s anyway on this build).
5. **Health probe:** no `/_health/` endpoint on this build → probe `/` (200).
6. **Rollouts linger on terminate** (meshed pods) — don't wait on `rollout status`; `kubectl get pods` and
   force-delete the old one if needed (`--force --grace-period=0`).

## Instrumenting an app (Sentry SDK)

```python
import os, sentry_sdk
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),          # empty/unset = SDK no-op (dev-safe)
    environment=os.getenv("SENTRY_ENVIRONMENT", "weyland"),
    traces_sample_rate=0.0, send_default_pii=False,
)
```

- **DSN by location:** in-cluster apps use the **internal-service** DSN
  `http://<key>@glitchtip.weyland.svc.cluster.local:8000/<projectId>` (they can't resolve the `*.weyland.lab`
  ingress). Off-cluster apps (e.g. Hermes on CT 104, B52) use the **ingress** DSN
  `https://<key>@glitchtip.weyland.lab/<projectId>` — which needs the **mkcert root CA** in that host's trust
  store or the HTTPS POST fails TLS silently.
- **One project per app** (cleaner issue streams + per-app alerting; self-hosted GlitchTip has **no event
  quota**). The DSN is keyed by **project ID**, not name — renaming a project is safe. Today: project `1` =
  `weyland-tool-server`, project `2` = `weyland_dagster`.
- **⚠ Event-size drop (the big one):** apps with large dependency trees (Dagster: torch/transformers/…) bloat
  the SDK's **`modules` integration** (full installed-package list) past GlitchTip's event-size limit →
  GlitchTip **200s the ingest then silently DROPS the event**. The SDK reports `flushed` with no error, so it
  looks like it worked. **Fix:** `disabled_integrations=[ModulesIntegration()]` (keeps `logging`/`excepthook`,
  which capture the real failures). **Diagnose:** `sentry_sdk.init(dsn, debug=True)` shows the envelope POST;
  send a bare event (`default_integrations=False, auto_enabling_integrations=False`) — if *that* lands but the
  full one doesn't, it's payload size.
- **Test a wiring:** `kubectl exec -n weyland deploy/<app> -c <ctr> -- python -c "import os,sentry_sdk;
  sentry_sdk.init(os.environ['SENTRY_DSN']); sentry_sdk.capture_message('test', level='error');
  sentry_sdk.flush(10)"` → check the project's Issues.

## GlitchTip → Port (catalog)

Per **project** → **Alerts** → Create Alert (e.g. 1 event / 1 min, uptime unchecked) → recipient **General
Webhook** → the Port `glitchtip` data-source ingest URL. **Replicate the alert on each project.**

- The webhook payload is **Slack-attachment format**, not rich Sentry JSON: `.body.text="GlitchTip Alert"` +
  `.body.attachments[0]` with `.title` (issue title), `.title_link` (issue URL), `.color` (level), and
  `.fields[]` (Project / Environment / Server Name). No level/count/status — map what's there.
- Port blueprint `glitchtip_issue`; mapping keys off `.body.attachments[0]` (identifier = issue number from
  `.title_link | split("/") | last` — GlitchTip issue IDs are globally unique).
- Alerts evaluate on a **short schedule** (not instant); Port webhook DSs **don't replay** — fire a *new*
  unique error to test the mapping. GlitchTip → Port gotchas also pinned in [Port webhook notes].

## Pointers
- Manifests: `k8s/glitchtip/glitchtip.yaml`
- Apps wired: `services/weyland-tool-server/` (main.py + Dockerfile), `services/weyland-dagster/weyland_pipeline/__init__.py`
- Alerting on logs (sibling): Loki ruler → Alertmanager → Telegram (`k8s/loki/loki-rules-configmap.yaml`)
