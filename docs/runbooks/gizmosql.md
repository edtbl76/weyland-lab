# GizmoSQL — DuckDB served over Arrow Flight SQL (B65 Tier-2, #2)

**What:** an in-process **DuckDB** engine wrapped in an **Arrow Flight SQL server** ([GizmoSQL](https://github.com/gizmodata/gizmosql)), in ns `data-mesh`. It's the **single-node OLAP** half of the query layer — fast on the lake's columnar files; **Trino** is the distributed-federation half (see [arch.md §7a](../arch.md) for the decision matrix).

**Why GizmoSQL at all:** DuckDB's own JDBC driver is **embedded-only** (`jdbc:duckdb:<file>` — no `host:port`), so a remote client (IntelliJ/DataGrip) has nothing to connect to. GizmoSQL fronts the engine with a real Flight SQL `host:port`. Confirmed in DataGrip: its native DuckDB driver shows *"Unable to find remote host or port in the URL"* — there is no server mode.

**Data:** a **persisted DuckDB** on a PVC (`DATABASE_FILENAME=/data/weyland.duckdb`). The silver is materialised as **base tables** — one per current lakeFS Parquet file, in a **schema per domain** (`datasets_music.<ident>`, `datasets_health.<ident>`) — by `scripts/gen_gizmosql_init.py tables`. They read the *versioned* lakeFS data via the in-cluster gateway (which rogueone-direct can't — lakeFS ingress is forward-auth gated), then persist to the PVC so they survive restarts.

**Why tables, not views (the fix that mattered):** GizmoSQL's Flight SQL **`GetTables` surfaces base tables but NOT views**. DataGrip/IntelliJ build their tree from `getTables`, so DuckDB *views* were queryable-by-name yet **invisible in the IDE tree** (schemas showed, expanded to nothing). Materialising as tables makes them browsable *and* makes queries hit native columnar storage instead of re-reading Parquet every time. `INIT_SQL_COMMANDS` therefore no longer builds the catalog — it's minimal (httpfs + a DuckDB `memory_limit`); the tables are a separate one-shot/refresh materialise (below).

---

## Connect

- **IntelliJ / DataGrip (dim-6 dev access):** Drivers → add **Arrow Flight SQL JDBC** (Maven `org.apache.arrow:flight-sql-jdbc-driver:17.0.0`, class `org.apache.arrow.driver.jdbc.ArrowFlightJdbcDriver`). Data source URL:
  ```
  jdbc:arrow-flight-sql://mother:31337?useEncryption=false&user=weyland&password=weyland_dev_password
  ```
  No SSH tunnel/SSL (the NodePort is LAN-reachable; the app is plaintext — see security below). Creds are passed as **URL params** (the driver has no separate cred fields).
- **emit_duckdb (DataHub catalog):** the Dagster pod connects via ADBC Flight SQL (`grpc+tcp://gizmosql.data-mesh.svc:31337`) and catalogs the tables in the `datasets_*` schemas (platform `duckdb`, lineage ← `parquet`). Runs in `datahub_catalog_emit_job`.
- **CLI (in-pod, ad-hoc):** `datasets_music`/`datasets_health` tables browse in the IDE tree once materialised. To list them from SQL: `SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema LIKE 'datasets_%';`.

## Deploy

GitOps: `k8s/data-mesh/gizmosql.yaml` (Deployment + **`gizmosql-duckdb` PVC** + NodePort Service + `GizmosqlDown` PrometheusRule + a `startupProbe` for the slow first boot). The **secret is imperative** (carries the lakeFS keys — not in git). `INIT_SQL_COMMANDS` is the **generated materialise SQL** (schema + secret + `CREATE TABLE IF NOT EXISTS … AS SELECT read_parquet(...)` per file) — see below; don't hand-write it.

## Materialise / refresh the store

The catalog **is** in `INIT_SQL` — that's deliberate. GizmoSQL runs each *client* Flight SQL statement in an isolated session, so driving the DDL from a client fails ("Schema … does not exist" — the client's `CREATE SCHEMA`/`CREATE SECRET` isn't visible to the next `CREATE TABLE`). `INIT_SQL` runs the whole block in **one shared startup session** — the only place schema + secret + table DDL coexist. On the persisted DB, `CREATE TABLE IF NOT EXISTS` materialises **once on first boot** and is a no-op on every restart after.

Generate the SQL (in the user-code pod, which has `LAKEFS_*` + reaches the gateway), patch the secret from it, restart:

```
kubectl -n weyland exec -i deploy/dagster-user-code -- python - tables < scripts/gen_gizmosql_init.py > /tmp/gizmo-init.sql
```
```
kubectl -n data-mesh create secret generic gizmosql-secret --from-literal=GIZMOSQL_USERNAME=weyland --from-literal=GIZMOSQL_PASSWORD=weyland_dev_password --from-file=INIT_SQL_COMMANDS=/tmp/gizmo-init.sql --dry-run=client -o yaml | kubectl apply -f -
```
```
kubectl -n data-mesh rollout restart deploy/gizmosql
```

- **First boot is the slow one** (CTAS reads every Parquet, incl. usda ~26M rows) — the `startupProbe` (20 min) covers it. Restarts after are instant (`IF NOT EXISTS` skips the persisted tables).
- **Refresh** (silver changed): `IF NOT EXISTS` won't update a table whose data changed. Simplest = **full reset**: `kubectl -n data-mesh delete pvc gizmosql-duckdb`, let it recreate, restart → re-materialise. Targeted = drop the stale table then restart (INIT_SQL recreates just it).
- **`SET memory_limit='3GB'`** leads the INIT_SQL — DuckDB otherwise sizes to node RAM and OOMs the 4Gi container during CTAS.

## Gotchas (every one cost us a cycle)

1. **`GIZMOSQL_PORT … not a valid integer` → CrashLoop.** k8s injects Docker-link service env vars (`GIZMOSQL_PORT=tcp://<ip>:31337`) for the same-named Service, colliding with GizmoSQL's own `GIZMOSQL_PORT` config var. Fix: **`enableServiceLinks: false`** on the pod.
2. **New pod can't schedule (Pending) after a fix.** The node runs ~98% CPU-committed, so a RollingUpdate double-books the CPU request and the new pod never schedules while the old (even crashing) one holds its slot. Fix: **`strategy: { type: Recreate }`** — kill old before new. (See [[k8s-rwo-recreate-strategy]].)
3. **`HTTP 400 … No region is provided`** reading the lake. DuckDB's S3 signature needs a region even against lakeFS. Add **`REGION 'us-east-1'`** to the `CREATE SECRET`.
4. **`schema mismatch in glob`** on `fma_echonest`/`fma_tracks` (historical). Old view SQL globbed a whole dir (`.../<table>/*.parquet, union_by_name=true`), and accumulated multi-run files → **duplicate rows** + schema drift. **Resolved**: the transform now writes one deterministic file per table (silver is clean), and `gen_gizmosql_init.py` materialises **one table per current Parquet file** (no glob, no `union_by_name`) — so no dup rows and no drift.
5. **`UNAVAILABLE: Network closed`** from the client. GizmoSQL **auto-generates a self-signed cert and serves TLS by default** (`grpc+tls://`). Either connect with TLS (and the client must skip verify), or run plaintext (below).

## Security model

- GizmoSQL runs **`TLS_ENABLED=0` (plaintext, `grpc+tcp://`)** and is **in the Istio mesh** (`sidecar.istio.io/inject: "true"`). The **in-cluster hop (emit_duckdb) is Istio mTLS** — so the ADBC client carries **no `TLS_SKIP_VERIFY`** (it was a flagged finding; resolved by the mesh, not papered over).
- **Open item (Phase 2):** the **external IDEA→NodePort hop is plaintext over the LAN** (password in the clear). The fix is a **gRPC-TLS ingress at `gizmosql.weyland.lab`** (Traefik terminates the real wildcard cert, forwards h2c into the mesh) → IDEA connects TLS with a valid cert, no skip-verify. Tracked in B69; low risk on a trusted home LAN, but it's the honest finish.

## Monitor

`GizmosqlDown` PrometheusRule (`kube_deployment_status_replicas_available{deployment="gizmosql"} == 0`, 5m → Alertmanager→Telegram). GizmoSQL exposes no `/metrics` and Flight SQL is gRPC (no HTTP page), so deployment-availability is the right signal; an optional Kuma **TCP** monitor on `mother:31337` is the shallow LAN ping.
