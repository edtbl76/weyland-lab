# Apache Ranger — data-plane authz for Trino (L5, Slice A)

**What:** Apache Ranger governs Trino access — table/column/row policies, **column masking**, row filters, and
(later) audit — for the `iceberg.dbt.*` marts and everything else Trino federates. It's Slice A of the L5
(Governance/Security) layer (Ranger + OPA + Soda).

**Where:**
- UI: **https://ranger.weyland.lab** (Keycloak forward-auth, then Ranger's own `admin` login). On the Tools launchpad.
- In-cluster: `ranger-admin.data-mesh.svc.cluster.local:6080` (REST API + the Trino plugin's policy source; the
  forward-auth ingress **401s API calls**, so automation uses the svc).
- Manifests: `k8s/data-mesh/ranger.yaml` (Ranger Admin) · `k8s/data-mesh/trino-ranger.yaml` (Trino plugin config) ·
  the ranger mounts in `k8s/data-mesh/trino.yaml`. Image build: `services/ranger/Dockerfile`.
- Codified authz setup: `scripts/ranger_setup.py`.
- **Creds:** admin / `Weyland_dev_password1` (Ranger UI users need upper+lower+digit — the shared
  `weyland_dev_password` is rejected; the *DB* role password stays `weyland_dev_password`).

## Architecture

Ranger Admin 2.6.0 (JVM/Tomcat; image `registry.weyland.lab/ranger:2.6.0-ubuntu24-r2` (r1 since B221; r2 2026-10-30: the libbrotli1 fix): the Ranger tree
from `mr3project/ranger:2.6.0` on Ubuntu 24.04 LTS + Temurin Java 8 + Python 3.12, see `services/ranger/Dockerfile`)
with policy DB in **weyland-postgres**
(`ranger` DB, role `rangeradmin`). Trino 468 has a **native** Ranger access control plugin
(`access-control.name=ranger`) that pulls policies from Ranger Admin every 30s and enforces them on every query.
Meshed (istio) so it reaches STRICT-mTLS Postgres.

## Rebuild from scratch

1. **Policy DB** (on **mother** — psql over the pod's local socket bypasses STRICT mTLS):
   ```
   kubectl -n weyland exec -i $(kubectl -n weyland get pod -l app=weyland-postgres -o jsonpath='{.items[0].metadata.name}') -c postgres -- bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d postgres' <<'SQL'
   CREATE ROLE rangeradmin LOGIN PASSWORD 'weyland_dev_password';
   ALTER ROLE rangeradmin CREATEDB CREATEROLE;
   CREATE DATABASE ranger OWNER rangeradmin;
   SQL
   ```
2. **Build + push the image** (on **rogueone**). B92 moved this off the local `ctr`-import onto the registry — a
   pruned local-only image left Ranger unable to restart at all (`Init:ImagePullBackOff`, nothing to pull from):
   **Take the next FREE tag — never rebuild one that exists.** The deployed image is `2.6.0-ubuntu24-r1` (B221) and
   `2.6.0-py3-r2` (Debian 11, B220) is its rollback; a push silently overwrites an existing tag. List them first:
   ```
   curl -s https://registry.weyland.lab/v2/ranger/tags/list
   ```
   then build the next one (here `ubuntu24-r2`) from the platform dir and point `ranger.yaml` at it (both `image:` lines):
   ```
   cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform && docker build -t registry.weyland.lab/ranger:2.6.0-ubuntu24-r2 services/ranger && bash /home/edwardmangini/IdeaProjects/weyland/scripts/push-image.sh registry.weyland.lab/ranger:2.6.0-ubuntu24-r2
   ```
   `scripts/build-push-images.sh` builds ranger only when `RANGER_TAG` names that next tag.
3. **Deploy** (on **mother**):
   ```
   kubectl apply -f ~/ranger.yaml
   kubectl -n data-mesh logs -f deploy/ranger-admin -c ranger-admin
   ```
   Watch for: Postgres schema load (`ranger_core_db_postgres.sql imported successfully`), `Ranger all admins
   default password change request processed successfully`, `Installation ... completed`, Tomcat binding
   `0.0.0.0:6080`. (The "failed to start!" line from `ranger-admin-services.sh` is a premature check — the webapp
   keeps booting; readiness on `/login.jsp` confirms.)
4. **Codify the Trino service + policies + mask** (on **mother** — needs the trino service to exist and Trino to be
   wired, step 5 first for the plugin, but the service/policies can be created any time):
   ```
   kubectl -n weyland exec -i deploy/dagster-user-code -- env RANGER_ADMIN_PASSWORD="$RANGER_ADMIN_PASSWORD" python - < scripts/ranger_setup.py
   ```
5. **Wire Trino** — `trino-ranger.yaml` + the mounts in `trino.yaml` (already committed). Apply + restart:
   ```
   kubectl apply -f ~/trino-ranger.yaml -f ~/trino.yaml
   kubectl -n data-mesh rollout restart deploy/trino
   ```
   ⚠ **Run `ranger_setup.py` (step 4) BEFORE this**, or the default-deny plugin locks every consumer out of Trino.

## Config change (edit install.properties / any ConfigMap)

**Passwords are NOT in the ConfigMap (B92).** `install.properties` ships `@@TOKEN@@` placeholders; the 9 real values live
in the **`ranger-admin-secret`** SealedSecret (data-mesh), and the **`render-install-props` initContainer** copies the
template and `sed`s each token in (`envFrom` the secret) into a writable emptyDir the main container mounts as `key/` —
the ConfigMap mount is read-only, so it can't be edited in place.
- **Non-password config** → edit the ConfigMap in `ranger.yaml` as usual.
- **A password** → re-seal `ranger-admin-secret` with the changed key (`kubectl create secret generic … --dry-run=client
  -o yaml | kubeseal --format yaml`, all 9 keys, on mother) and commit the sealed CR — never put the value back in the
  ConfigMap. A *new* password also needs its `@@TOKEN@@` in the template plus a matching `-e "s|@@TOKEN@@|${VAR}|"` in
  the initContainer's `sed`.

ConfigMap changes don't restart the pod — force it:
```
kubectl apply -f ~/ranger.yaml && kubectl -n data-mesh rollout restart deploy/ranger-admin
```

## The gotcha gauntlet (why the manifests look the way they do)

- **Image config contract (the mr3project/ranger:2.6.0 tree, kept as-is by B221's rebase):** `install.properties` mounts as the **`/opt/mr3-run/ranger/key/`
  dir** (NOT `ranger-admin/`); the image also needs a **`/opt/mr3-run/ranger/conf/`** dir (krb5.conf, log4j,
  `ranger-admin-site.xml.append`) it doesn't ship — both are ConfigMaps.
- **The image (B221, 2026-10-20):** the Ranger 2.6.0 tree is copied UNCHANGED out of `mr3project/ranger:2.6.0` (Debian
  11, end of life) onto Ubuntu 24.04 LTS with Temurin Java 8 (install.properties requires 1.8) and Python 3.12
  (`db_setup.py` is python3, stdlib only). Every input is pinned by digest. The bundled Solr (unused: `audit_store` is
  empty) and MSSQL driver are dropped; Postgres JDBC is `postgresql-42.7.14.jar` (checksum-verified at build), which
  `SQL_CONNECTOR_JAR` names. `PYTHONWARNINGS=ignore::SyntaxWarning` silences ~200 per-boot warnings Python 3.12+ prints
  for `db_setup.py`'s old string escapes (they contain "[E]"/"error", which log alerts match). Trivy: 0 HIGH/CRITICAL
  OS findings; the 266 left are Ranger 2.6.0's own bundled jars, which only an Apache release can fix, and even
  `apache/ranger:2.9.0` carries 251. Ubuntu, not Debian 13: `debian:trixie-slim` itself showed 43 unfixed HIGH.
  **Roll back** = `2.6.0-py3-r2` on both `image:` lines AND `SQL_CONNECTOR_JAR` back to `postgresql-42.3.2.jar`.
- **`ranger-admin-site.xml.append` is load-bearing:** `start-ranger.sh` deletes the original `</configuration>`
  and splices this file in, so it MUST set `ranger.service.host` (else Tomcat "Host name is required") AND re-close
  `</configuration>`. Keep the YAML block-scalar indentation consistent.
- **Password policy:** Ranger UI users require upper+lower+digit → `Weyland_dev_password1`.
- **http→https redirect middleware:** Ranger's Tomcat ignores `X-Forwarded-Proto` and emits absolute `http://`
  redirects to `/login.jsp`, downgrading off https → forward-auth builds an `http` redirect_uri that Keycloak's
  https-only client rejects ("Invalid parameter: redirect_uri"). Fixed by a `redirectScheme:https` Middleware
  chained **before** forward-auth on the ingress.
- **Trino plugin config = ABSOLUTE paths:** `ranger.plugin.config.resource=/etc/trino/ranger-trino-security.xml,...`
  (Trino treats them as files, not classpath; bare names → "file does not exist").
- **DEFAULT-DENY lockout:** the moment Trino loads the plugin, unlisted access is denied. Mesh consumers log in as
  varied users (`dbt`, `cube`, `datahub`, `mcp`, `notebook`, … — [trino.md](trino.md) § Authentication). The service's
  13 default policies grant to user `trino` only → `ranger_setup.py` adds group `public` to them all before enabling.
  Rollback = remove the access-control.properties mount from `trino.yaml` + restart Trino.
- **Impersonation is a policy, and it was wide open (B233, 2026-10-23).** A Trino login may name a different session user
  (`X-Trino-User`); Ranger decides it with the `all - trinouser` policy. Broadening it to `public` for user `*` meant any
  login could become anyone — `analyst` claiming `dbt` ran as dbt and read past its mask (proven on a throwaway Trino 468
  with the live policies). The plugin checks impersonation even when login == user, so an empty policy locks everyone
  out. `ranger_setup.py`'s `restrict_impersonation_to_self()` sets it to the `{USER}` macro for `public` (each login may
  become only itself), and `broadened()` never touches it again. Tests: `scripts/tests/test_ranger_setup.py`.
- **The Trino resource lookup** (policy-editor autocomplete) logs in as `ranger` over HTTPS 8443 (`TRINO_PW_RANGER`,
  passed to `ranger_setup.py`; the lab CA mounted at `/etc/weyland-ca` in ranger-admin). Trino's front door had never
  admitted Ranger Admin, so the lookup failed from B211 (2026-10-14) until B233 admitted it on 8443.
- **Masking user must exist:** a policy referencing user `analyst` 400s until the user is created
  (`POST /service/xusers/secure/users`, ROLE_USER) — `ensure_user()` handles it.
- **Memory:** Ranger Admin ~2 Gi. On the tight node (steady ~69%) a deploy-window confluence (Ranger warm + DataHub
  kafka/system-update + apt) OOM'd mother once. Grow vm-101 RAM before adding more L5 services.

## Verify

Column mask working, and a claimed identity refused (B233: every caller logs in over HTTPS; the pod holds the `dbt`
login, and the `analyst` password is passed through from `scripts/.env`):
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && kubectl -n weyland exec -i deploy/dagster-user-code -- env TRINO_PW_ANALYST="$TRINO_PW_ANALYST" python - <<'PY'
import os, trino
from trino.auth import BasicAuthentication as B
PW = {"analyst": os.environ["TRINO_PW_ANALYST"], "dbt": os.environ["TRINO_PASSWORD"]}
def q(login, as_user=None):
    c = trino.dbapi.connect(host="trino.data-mesh.svc.cluster.local", port=8443, http_scheme="https",
                            verify="/etc/weyland-ca/rootCA.pem", user=as_user or login, auth=B(login, PW[login]),
                            catalog="iceberg", schema="dbt")
    try:
        cur = c.cursor(); cur.execute("SELECT state, year, depression_pct FROM mart_state_health_trends ORDER BY state LIMIT 3")
        return cur.fetchall()
    except Exception as e:
        return "REFUSED: " + str(e).splitlines()[0][:90]
print("analyst (masked)     :", q("analyst"))                 # depression_pct -> None
print("dbt (unmasked)       :", q("dbt"))                     # real values
print("analyst claiming dbt :", q("analyst", as_user="dbt"))  # REFUSED ... cannot become user dbt
PY
```
