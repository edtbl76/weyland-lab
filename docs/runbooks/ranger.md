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

Ranger Admin (JVM/Tomcat, image `mr3project/ranger:2.6.0` + python3) with policy DB in **weyland-postgres**
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
2. **Build + import the image** (on **mother** — base is Docker Hub, builds fine here):
   ```
   docker build -t weyland/ranger:2.6.0-py3 services/ranger
   docker save weyland/ranger:2.6.0-py3 | sudo ctr -n k8s.io images import -
   ```
   (rsync `services/ranger/` to mother first if it's not there.)
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
   kubectl -n weyland exec -i deploy/dagster-user-code -- python - < scripts/ranger_setup.py
   ```
5. **Wire Trino** — `trino-ranger.yaml` + the mounts in `trino.yaml` (already committed). Apply + restart:
   ```
   kubectl apply -f ~/trino-ranger.yaml -f ~/trino.yaml
   kubectl -n data-mesh rollout restart deploy/trino
   ```
   ⚠ **Run `ranger_setup.py` (step 4) BEFORE this**, or the default-deny plugin locks every consumer out of Trino.

## Config change (edit install.properties / any ConfigMap)

ConfigMap changes don't restart the pod — force it:
```
kubectl apply -f ~/ranger.yaml && kubectl -n data-mesh rollout restart deploy/ranger-admin
```

## The gotcha gauntlet (why the manifests look the way they do)

- **Image config contract (mr3project/ranger:2.6.0):** `install.properties` mounts as the **`/opt/mr3-run/ranger/key/`
  dir** (NOT `ranger-admin/`); the image also needs a **`/opt/mr3-run/ranger/conf/`** dir (krb5.conf, log4j,
  `ranger-admin-site.xml.append`) it doesn't ship — both are ConfigMaps.
- **python3:** base ships only python2.7; Ranger 2.6 `db_setup.py` is python3 → baked into the image
  (`services/ranger/Dockerfile`). Postgres JDBC is already bundled (`/opt/mr3-run/lib/postgresql-42.3.2.jar`).
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
- **DEFAULT-DENY lockout:** the moment Trino loads the plugin, unlisted access is denied. Mesh consumers use varied
  users (dbt=`dbt`, lightdash=`lightdash`, DataHub=`trino`). The service's 13 default policies grant to user `trino`
  only → `ranger_setup.py` adds group `public` to them all before enabling. Rollback = remove the
  access-control.properties mount from `trino.yaml` + restart Trino.
- **Masking user must exist:** a policy referencing user `analyst` 400s until the user is created
  (`POST /service/xusers/secure/users`, ROLE_USER) — `ensure_user()` handles it.
- **Memory:** Ranger Admin ~2 Gi. On the tight node (steady ~69%) a deploy-window confluence (Ranger warm + DataHub
  kafka/system-update + apt) OOM'd mother once. Grow vm-101 RAM before adding more L5 services.

## Verify

Column mask working (on **mother**):
```
kubectl -n weyland exec -i deploy/dagster-user-code -- python - <<'PY'
import trino
def q(u):
    c=trino.dbapi.connect(host="trino.data-mesh.svc.cluster.local", port=8080, user=u, catalog="iceberg", schema="dbt")
    cur=c.cursor(); cur.execute("SELECT state, year, depression_pct FROM iceberg.dbt.mart_state_health_trends ORDER BY state LIMIT 3"); return cur.fetchall()
print("analyst (masked):", q("analyst"))   # depression_pct -> None
print("dbt (unmasked)  :", q("dbt"))        # real values
PY
```
