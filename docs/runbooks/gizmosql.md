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

GitOps: `k8s/data-mesh/gizmosql.yaml` (Deployment + **`gizmosql-duckdb` PVC** + NodePort Service + `GizmosqlDown` PrometheusRule). The **secret is imperative** (carries the lakeFS keys — not in git). `INIT_SQL_COMMANDS` is now **minimal**: it does NOT build the catalog (the tables persist on the PVC + are materialised separately), only `INSTALL httpfs` and cap DuckDB's memory (default is node-RAM-sized → would OOM the 4Gi container):

```
kubectl -n data-mesh create secret generic gizmosql-secret --from-literal=GIZMOSQL_USERNAME=weyland --from-literal=GIZMOSQL_PASSWORD=weyland_dev_password --from-literal=INIT_SQL_COMMANDS="INSTALL httpfs; LOAD httpfs; SET memory_limit='3GB';" --dry-run=client -o yaml | kubectl apply -f -
```

## Materialise / refresh the store

The catalog is **not** in `INIT_SQL` anymore — it's a one-shot (and the refresh after any dataset change). `gen_gizmosql_init.py tables` runs in the user-code pod (which has both `LAKEFS_*` to LIST Parquet and `GIZMOSQL_*` to connect), connects over Flight SQL, and `CREATE OR REPLACE TABLE`s one persisted table per current silver Parquet file into `datasets_music`/`datasets_health`. Per-table try/except → one bad file logs + is skipped, not aborting the run.

```
kubectl -n weyland exec -i deploy/dagster-user-code -- python - tables < nodes/mother/lab/weyland-platform/scripts/gen_gizmosql_init.py
```

- **Refresh** (silver changed): re-run the same command — `CREATE OR REPLACE` swaps each table in place.
- **Full reset**: `kubectl -n data-mesh delete pvc gizmosql-duckdb` + let it recreate, restart gizmosql, re-materialise.
- **First materialise is the slow one** (reads every Parquet); restarts after are instant (tables are on the PVC).

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
