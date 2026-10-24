# Trino — federation query engine (B65 Tier-2, 1st)

Single-node Trino in `data-mesh`. The keystone the lab queries the lake + relational stores through;
Superset / dbt / the B73 "use the data" work all ride on it. Manifest: `k8s/data-mesh/trino.yaml`
(deployed by the data-mesh Argo app). Always-on (~2 GB heap) — revisit KEDA at the footprint gate.

## Catalogs
- **`iceberg`** — the Nessie lake (`datasets.*` music gold, `catalog`, `eval`). **Uses Trino's NATIVE
  Nessie catalog** (`iceberg.catalog.type=nessie`, Nessie API v2), NOT the generic `type=rest` — the
  generic REST client forges a 403 at init against Nessie's `/iceberg` even though the infra is clean.
  See [[trino-nessie-native-catalog]].
- **`postgresql`** — the `weyland` DB (JDBC; works over the mesh to STRICT Postgres — it's TCP, so Istio
  passes it through).
- `system` — Trino internals.

## How to connect
Since B233 (2026-10-23) Trino authenticates: every caller logs in with its own password, and a password is accepted
**only over HTTPS on 8443** (a cert from the lab's mkcert CA). See § Authentication.
- **CLI:** `kubectl -n data-mesh exec -it deploy/trino -- trino` → `trino>` prompt (inside the coordinator; the CLI
  talks to its own loopback HTTP port, so it is not a remote caller).
- **IntelliJ (Database tool):** a **Trino** data source at the `trino-lan` NodePort over TLS (the cert names
  `192.168.1.243`), login `emangini` (`TRINO_PW_EMANGINI` in `scripts/.env`):
  `jdbc:trino://192.168.1.243:30843?SSL=true&SSLVerification=FULL&SSLTrustStorePath=/home/edwardmangini/.local/share/mkcert/rootCA.pem`.
  The `SSLTrustStorePath` is required: IntelliJ runs its own bundled Java, which does NOT read rogueone's system trust
  store (`mkcert -install`), so without it the first query fails "unable to find valid certification path"
  (2026-10-23). The live data source (`.idea/dataSources.xml`, gitignored) is authentication **No auth** with
  `&user=emangini&password=…` in the URL, because the data-source dialog took no keyboard input; with No auth IntelliJ
  passes no separate credentials, so the driver's "password is both in the URL and an argument" error cannot occur.
  The JDBC driver refuses a password over plain HTTP ("TLS/SSL is required"); the old plain-HTTP `:30808` NodePort
  was removed in stage 3. Admitted for rogueone only (`netpol-trino.yaml`). The Trino data source uses the NodePort.
  An IntelliJ data source's own Kubernetes connection is also allowed (AGENTS.md's one exception), but for Trino it
  would land on plain-HTTP 8080, which since stage 3 refuses everything except the UI path — so Trino is the NodePort.
- **Web UI:** `https://trino.weyland.lab` (forward-auth → Keycloak). Trino's own UI login is off: the UI runs as the
  fixed identity `trino-ui` (`web-ui.authentication.type=fixed`), because Keycloak already gates the page to the owner
  (owner decision, 2026-10-23). It's a **monitoring console** (running queries, timings, cluster), NOT a query editor —
  use Superset/CLI/IDE to run SQL.

## Authentication (B233, 2026-10-23)

**Why.** Trino 468 had no authenticator: every client set `X-Trino-User` and Trino believed it, so Ranger's per-user
policies (the `analyst` column mask, any future row filter) could be bypassed by claiming another name. The network
front door (`netpol-trino.yaml`, B211) limited who could connect, never who they were. Two things had to change, and
either alone does nothing:
1. **A password per caller** (Trino's file authenticator, bcrypt hashes in `password.db`), over **HTTPS only**. In Trino
   468 `http-server.authentication.allow-insecure-over-http=true` does NOT mean "check passwords over HTTP": it means
   "on HTTP, skip authentication and trust the header" (a no-credential request got 200 on the throwaway). With it
   `false`, plain HTTP refuses everything except a request that says it arrived over HTTPS (`X-Forwarded-Proto`, which
   Traefik sets for the UI path).
2. **Ranger's impersonation policy narrowed.** A login may still *name* a different session user; Ranger's
   `all - trinouser` policy decides it, and `ranger_setup.py` had opened it to group `public` for every user (`*`) — so
   a password alone would have let `analyst` log in and claim `dbt` (proven on the throwaway: it ran as dbt). The
   plugin checks impersonation even when login == user, so removing `public` locks everyone out; the fix is the `{USER}`
   macro: each login may become only itself (`restrict_impersonation_to_self()`, tests in
   `scripts/tests/test_ranger_setup.py`).

**The identities** — one per caller, the password in `scripts/.env` as `TRINO_PW_<ID>`
(`scripts/trino-credentials.sh`):

| Login | Caller | Where the credential lives |
|---|---|---|
| `dbt` | Dagster user-code (dbt, the mart export, Feast, Soda, GE) + dbt-docs | `weyland/trino-dbt` → `TRINO_USER` / `TRINO_PASSWORD` |
| `cube` | Cube | `data-mesh/trino-cube` → `CUBEJS_DB_USER` / `CUBEJS_DB_PASS` |
| `datahub` | DataHub managed ingestion (`trino.recipe.yaml`) | `data-mesh/trino-datahub` → `TRINO_DATAHUB_PASSWORD` on datahub-actions |
| `datahub-coverage` | the coverage CronJob (ns weyland) | `weyland/trino-datahub-coverage` |
| `mcp` | trino-mcp | `weyland/trino-mcp` |
| `prometheus` | the ServiceMonitor scrape (`/metrics` needs a login) | `data-mesh/trino-metrics-auth` |
| `notebook`, `analyst` | the JupyterHub servers (notebook 72 uses both) | `jupyterhub/trino-notebook`, `jupyterhub/trino-analyst` |
| `perf` | the on-demand k6 baseline Job | `data-mesh/trino-perf` |
| `lightdash`, `superset` | the BI tools | entered in each app's UI (stored in its own DB) |
| `emangini` | IntelliJ (Database tool) on rogueone | the IDE's data source |
| `ranger` | Ranger Admin's resource lookup | Ranger's `trino` service config (`ranger_setup.py`) |

Trino's side is `data-mesh/trino-auth`: `password.db`, `tls.pem` (mkcert key + cert for
`trino.data-mesh.svc.cluster.local`, `trino.data-mesh.svc`, `trino.data-mesh`, `trino`, `192.168.1.243`; expires
**2029-01-23**) and `TRINO_SHARED_SECRET` (internal communication, required once an authenticator is on). Every client
verifies Trino's cert against `weyland-mkcert-ca` mounted at `/etc/weyland-ca` (Superset: `/etc/ssl/weyland-ca`).
Client quirks, all proven against a throwaway Trino 468 with the live Ranger policies:
- **Cube's** base driver defaults `rejectUnauthorized` to **false** — `CUBEJS_DB_SSL_REJECT_UNAUTHORIZED=true` is
  load-bearing (without it Cube connected with no CA at all).
- **Soda** and **GE** have no CA option: `soda_scan_op` / `ge_validate_op` set `REQUESTS_CA_BUNDLE` for their
  subprocess only (`trino_auth.subprocess_env()`); Soda resolves `${TRINO_PASSWORD}`; GE keeps the placeholder in its
  stored datasource and uses `add_or_update_sql` (its file context had kept its first connection string forever).
- **trino-mcp**, **k6** and BusyBox **wget** are Go / OpenSSL clients with no CA flag: `SSL_CERT_FILE` points them at
  the lab CA (each refuses the cert without it).
- **Lightdash** passes no TLS options: `NODE_EXTRA_CA_CERTS` adds the lab CA to Node's store.
- **DataHub's actions image** sets `REQUESTS_CA_BUNDLE` to the system bundle, and in `requests` an environment bundle
  overrides a client's own `verify` path — so the recipe's `connect_args.verify` was silently ignored and the Trino
  source failed `CERTIFICATE_VERIFY_FAILED` on its first live run. `datahub-values.yaml` builds a combined bundle (system
  CAs + the lab root) in an init container and points `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` at it. Any client in an image
  that sets that variable needs the same treatment.
- **Trino JDBC** (IntelliJ, Ranger's lookup driver 451) detects a PEM truststore itself; `SSLTrustStoreType=PEM` fails.

**Roll it out, in this order.** Stages 1-2 change nothing a caller notices: plain HTTP on 8080 keeps trusting
`X-Trino-User` while every caller moves to 8443 (proven: both doors work at once). Stage 3 closes 8080. **All three
stages are done (2026-10-23)**; the steps stay here for a rebuild or a re-run.

*Stage 1-2 — credentials, then the push.*
1. The passwords and the shared secret into `scripts/.env` (generated, never printed):

   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/scripts/trino-credentials.sh generate
   ```
2. Trino's password file and the mkcert cert, into a private dir:

   [rogueone]
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/scripts/trino-credentials.sh build /home/edwardmangini/.trino-auth-build
   ```
3. The Secrets (from files; checks every stored length):
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/scripts/trino-credentials.sh apply /home/edwardmangini/.trino-auth-build
   ```
4. Seal them into the repo (`k8s/sealed-secrets/sealed/`):
   ```
   bash /home/edwardmangini/IdeaProjects/weyland/scripts/trino-credentials.sh seal
   ```
5. Remove the build dir (the key and hashes now live only in the sealed Secret):

   [rogueone]
   ```
   rm -r /home/edwardmangini/.trino-auth-build
   ```
6. Ranger: the impersonation policy and the lookup login. `ranger_setup.py` needs `RANGER_ADMIN_PASSWORD`; if
   `scripts/.env` lacks it, copy it from the cluster Secret first (not printed):
   ```
   grep -q '^RANGER_ADMIN_PASSWORD=.' /home/edwardmangini/IdeaProjects/weyland/scripts/.env || printf 'RANGER_ADMIN_PASSWORD=%s\n' "$(kubectl -n data-mesh get secret ranger-admin-secret -o jsonpath='{.data.RANGER_ADMIN_PASSWORD}' | base64 -d)" >> /home/edwardmangini/IdeaProjects/weyland/scripts/.env
   ```
   ```
   set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && kubectl -n weyland exec -i deploy/dagster-user-code -- env RANGER_ADMIN_PASSWORD="$RANGER_ADMIN_PASSWORD" TRINO_PW_RANGER="$TRINO_PW_RANGER" python - < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/ranger_setup.py
   ```
   Expect `impersonation policy 1: now {USER} only` (or `already self-only`) and `ranger trino setup done`. Safe before
   the push: on the old door the claimed user IS the login, so `{USER}` grants exactly what every caller does today.
7. Push (the sealed files with the manifests and code), CI, then `ship-images.sh` (Dagster user-code). Argo rolls
   Trino, Cube, trino-mcp, dbt-docs, datahub-actions, Lightdash, Ranger Admin and the JupyterHub config.
   **Expect a short default-deny window when Trino and Ranger Admin restart together** (2026-10-23: 90 s, 15:32:54 →
   15:34:25). The Trino plugin's policy cache lives in the container's `/tmp`, so a fresh Trino pod has no policies
   until Ranger Admin answers; meanwhile every query is denied ("Principal X cannot become user X"), and trino-mcp,
   which tests Trino once at start, crash-loops until then. It clears by itself; confirm with
   `kubectl -n data-mesh logs deploy/trino -c trino --since=10m | grep "Switched policy engine"` (a version, not `[-1]`).
8. The callers that store their connection themselves (UI steps):
   - **DataHub:** Ingestion → Sources → `trino` → Edit → the YAML: paste `k8s/data-mesh/datahub-ingestion/trino.recipe.yaml`'s
     `source:` block → Save. Then **Run** it.
   - **Superset:** Settings → Database Connections → the Trino database → Edit → SQLAlchemy URI
     `trino://superset@trino.data-mesh.svc.cluster.local:8443/iceberg`, password `TRINO_PW_SUPERSET`; Advanced → Other
     → Engine parameters `{"connect_args": {"http_scheme": "https", "verify": "/etc/ssl/weyland-ca/rootCA.pem"}}` →
     Test connection → Finish.
   - **Lightdash:** Project settings → warehouse connection (Trino): host `trino.data-mesh.svc.cluster.local`, port
     `8443`, user `lightdash`, password `TRINO_PW_LIGHTDASH`, HTTP scheme `https` → Test and save.
   - **IntelliJ** (Database tool → the Trino data source → Properties): the URL in § How to connect (with
     `SSLTrustStorePath`), user `emangini`, password `TRINO_PW_EMANGINI`.
   The values come from `scripts/.env` (`grep '^TRINO_PW_SUPERSET=' …` shows only the line you need).
9. Live checks (§ Check it below), every caller on demand: dbt (`weyland_dbt_job`), the Soda and GE jobs, the mart
   export, Cube (a Playground query), trino-mcp through Bifrost, DataHub's Trino source run, the coverage CronJob
   (`kubectl create job --from`), notebooks 20/40/62/71/72/81, the perf baseline, Prometheus `up`, the Trino UI.

*Stage 3 — close the old door* (a separate push, after every check in 9 passes; done 2026-10-23):
`allow-insecure-over-http=false`, 8080 admits only Traefik (the UI path) in `netpol-trino.yaml`, the `:30808` NodePort
and the no-auth proxy removed (the Lightdash Argo app's proxy source dropped; `prune: true` deleted its resources), the
notebook entry narrowed to the owner's server (`hub.jupyter.org/username`). Proven on the throwaway with the manifest's
config: UI through Traefik 200, plain HTTP claiming `dbt` 403, Traefik's header with no credential 401.

**Check it.** From any admitted pod (e.g. dagster-user-code), with no credential and claiming a privileged user —
expect 401:
```
kubectl -n weyland exec deploy/dagster-user-code -- python -c "import trino;c=trino.dbapi.connect(host='trino.data-mesh.svc.cluster.local',port=8443,user='dbt',http_scheme='https',verify='/etc/weyland-ca/rootCA.pem').cursor();c.execute('select 1');print(c.fetchall())"
```
And the pod's own login — expect `[['dbt']]`:
```
kubectl -n weyland exec deploy/dagster-user-code -- python -c "from weyland_pipeline.trino_auth import connect;c=connect().cursor();c.execute('select current_user');print(c.fetchall())"
```
The impersonation policy as Trino holds it (`{USER}` on policy 1):
```
kubectl -n data-mesh exec deploy/trino -c trino -- sh -c 'cat /tmp/ranger/trino/policycache/trino_trino.json' | python3 -c "import sys,json;[print(p['id'],p['resources']['trinouser']['values'],[i['groups'] for i in p['policyItems']]) for p in json.load(sys.stdin)['policies'] if 'trinouser' in p['resources']]"
```

**Rotate a login** (one identity; the others keep working): regenerate it, rebuild, re-apply, re-seal, push, then
restart that caller (and Trino, which reads `password.db` at start):

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/trino-credentials.sh generate --rotate cube
```
then steps 2-5 and 7 above, `kubectl -n data-mesh rollout restart deploy/trino` and the caller's restart (a UI-stored
login is re-entered in its UI). Rotating the cert is the same without `--rotate` (`build` re-issues it); do it before
2029-01-23.

**Roll back.** Stage 3: revert its commit (the old door reopens). Stages 1-2: revert the commit — Trino returns to no
authenticator and every caller to the old door (Argo `selfHeal` makes the git revert the only rollback; see project
rules). The Ranger `{USER}` policy can stay: it is correct with or without authentication.

## Gotchas (all cost time, all in the manifest now)
- **Native Nessie catalog**, not generic REST (above).
- **AVX/Proxmox:** Lance + other native libs need AVX-512 → required `cpu: host` on the mother VM
  ([[proxmox-vm-cpu-host-avx]]); unrelated to Trino but surfaced in the same push.
- **`http-server.process-forwarded=true`** — without it the web UI 406s behind Traefik+Istio
  ("Server configuration does not allow processing of the X-Forwarded-For header").
- **`/metrics` auth:** OpenMetrics needs an authenticated user. Since B233 the ServiceMonitor logs in as `prometheus`
  over HTTPS on 8443 (`basicAuth` → `trino-metrics-auth`, a real password; `tlsConfig` with the lab CA). Manual curl
  also needs `-H "Accept: text/plain"` (it 406s on `*/*`); Prometheus sends the right Accept itself.
- **No catalog auto-reload:** Trino reads catalogs/config at startup only → after a configmap change,
  `kubectl -n data-mesh rollout restart deploy/trino` (and the configmap must be synced/applied first).

## Observability
- **Prometheus** ServiceMonitor scrapes `/metrics` (basicAuth) → **4,228 `trino_*` series** (2,720 distinct
  metric names), ~6,721 samples/scrape. **Grafana → Dashboards → Trino** (uid `trino-b148`,
  `k8s/data-mesh/trino-dashboard.yaml`).
- **Istio** sidecar already exports request rate/latency/errors (`istio_requests_total{destination_workload="trino"}`).
- **Kuma** HTTP monitor on `https://trino.weyland.lab` (reports UP off the gated page, like the other SSO'd UIs).

> ### ⚠ This bullet was FALSE for 59 days (B148, fixed 2026-08-26)
>
> It said `trino_*` series were in Grafana. There were none — no series, no target, no scrape pool.
> **The `trino` Service had no `metadata.labels` block.** A ServiceMonitor's `selector.matchLabels`
> matches **Services by their own `metadata.labels`**; the `spec.selector` sitting right beside it
> matches **pods**. Both said `app: trino`, so the manifest read as correct. Nothing matched, so
> Prometheus built no scrape pool, so `up{job="trino"}` returned *no data* — which reads as "idle",
> not "broken". `kubectl get servicemonitor` said `60d` the whole time.
>
> **Two traps worth keeping:**
>
> 1. **Until B233 (2026-10-23) an empty password in `trino-metrics-auth` was CORRECT, not missing.** Trino's insecure
>    mode rejects any request that *carries* a password: `curl -u metrics:x` → **401
>    `Password not allowed for insecure authentication`**; `curl -u "metrics:"` → **200**. Since B233 the opposite
>    holds: the scrape is HTTPS on 8443 with the `prometheus` login's real password, and plain HTTP answers a
>    Basic-auth scrape with 401 (measured on the throwaway), which is why the ServiceMonitor moved port in the same push.
> 2. **Metric names carry a `_name_` segment** the JMX exporter inserts —
>    `trino_execution_name_QueryManager_RunningQueries`, not `trino_execution_QueryManager_RunningQueries`.
>    Guessing the shorter form returns "no such metric", which on a dashboard renders as an empty panel
>    and looks exactly like an idle cluster. Read them from
>    `/api/v1/label/__name__/values`, and check counter-vs-gauge in `/api/v1/metadata` before reaching
>    for `rate()`/`increase()`.
>
> **Recurrence guard:** `scripts/check-servicemonitor-coverage.sh` (CronJob `servicemonitor-coverage`,
> 02:45 NY) reconciles every ServiceMonitor against the workload it monitors. See
> [observability.md](observability.md) § ServiceMonitor coverage.

**Verify it end to end** (series, not just `up` — `up` alone was 1 for the istio sidecar throughout):

```
kubectl get --raw "/api/v1/namespaces/monitoring/pods/prometheus-monitoring-kube-prometheus-prometheus-0:9090/proxy/api/v1/query?query=count(%7B__name__%3D~%22trino_.%2B%22%7D)"
```

## Memory creep and the Sunday OOM (2026-10-21)

**What happened:** `weyland_dbt_job` failed on Sunday 10-11 and 10-18 with every test erroring at once, because Trino was
OOM-killed (`137`) at its 8Gi limit one minute into the 06:00 build. dbt was only the last straw: the container's working
set climbs **~0.4 GiB a day** after each restart (1.2 → 4.4 GiB over a week), all outside the 4G heap, so a week-old
Trino had no room for the build's peak. Measured 2026-10-21: a full `dbt build --threads 1` took 37 s and added ~1.9 GiB
(3.4 → 5.3 GiB).

**Fixed / under test:** dbt runs at `threads: 1` (`services/weyland-dagster/dbt/profiles.yml`), and the Trino container
sets `MALLOC_ARENA_MAX=2` (glibc's per-thread arenas are a common cause of JVM native growth). The second is an
experiment. Check the daily climb, 6-hourly, over the last week:
```
python3 -c "import json,urllib.request,urllib.parse,time;u='http://192.168.1.243:30909/api/v1/query_range?'+urllib.parse.urlencode({'query':'max(container_memory_working_set_bytes{namespace=\"data-mesh\",pod=~\"trino-.*\",container=\"trino\"})','start':time.time()-7*86400,'end':time.time(),'step':'6h'});[print(time.strftime('%m-%d %H:%MZ',time.gmtime(float(t))),round(float(v)/2**30,2)) for t,v in json.load(urllib.request.urlopen(u))['data']['result'][0]['values']]"
```
**Pass:** after a few days the working set stays roughly flat (well under ~0.4 GiB/day) between restarts. **Fail:** it
still climbs at the old rate. Then the next suspect is the Ranger plugin's native/GraalVM-Truffle memory (see the
`limits:` comment in `k8s/data-mesh/trino.yaml`, 2026-07-20), not the heap. Never raise `-Xmx` for this: the heap is not
what overflows. Restart count and last reason: `kubectl -n data-mesh get pod -l app=trino -o
jsonpath='{.items[0].status.containerStatuses[?(@.name=="trino")].lastState.terminated}'`.

## DataHub
DataHub `trino` ingestion source (`k8s/data-mesh/datahub-ingestion/trino.recipe.yaml`) catalogs the
`iceberg` catalog's tables as `trino`-platform datasets with **sibling + upstream lineage to the iceberg
platform** (`catalog_to_connector_details`) — Trino shows as the query layer over the lake. It logs in as `datahub`
over HTTPS (B233); the live source is UI state, so the recipe is pasted into it (§ Authentication step 8).

## Secrets (imperative → SealedSecrets at B69)
- `trino-secret` — MINIO_ACCESS_KEY / MINIO_SECRET_KEY / WEYLAND_PG_PASSWORD (catalog creds).
- `trino-auth` (B233) — `password.db`, `tls.pem`, `TRINO_SHARED_SECRET`; built by `scripts/trino-credentials.sh`.
- `trino-metrics-auth` — username=prometheus, its real password since B233 (it was empty in the no-auth era).
- One Secret per caller login (§ Authentication's table), all from `scripts/trino-credentials.sh`.
