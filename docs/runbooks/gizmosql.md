# GizmoSQL — DuckDB served over Arrow Flight SQL (B65 Tier-2, #2)

**What:** an in-process **DuckDB** engine wrapped in an **Arrow Flight SQL server** ([GizmoSQL](https://github.com/gizmodata/gizmosql)), in ns `data-mesh`. It's the **single-node OLAP** half of the query layer — fast on the lake's columnar files; **Trino** is the distributed-federation half (see [arch.md §7a](../arch.md) for the decision matrix).

**Why GizmoSQL at all:** DuckDB's own JDBC driver is **embedded-only** (`jdbc:duckdb:<file>` — no `host:port`), so a remote client (IntelliJ/DataGrip) has nothing to connect to. GizmoSQL fronts the engine with a real Flight SQL `host:port`. Confirmed in DataGrip: its native DuckDB driver shows *"Unable to find remote host or port in the URL"* — there is no server mode.

**Data:** in-memory DuckDB; `INIT_SQL_COMMANDS` runs on every start to `INSTALL httpfs` + create an S3 secret for the **lakeFS gateway** + `CREATE VIEW`s over the **current lakeFS Parquet** (`s3://music/main/parquet/<table>`). Being in-cluster, it reads the *versioned* lakeFS data via the gateway — which rogueone-direct can't (lakeFS ingress is forward-auth gated).

---

## Connect

- **IntelliJ / DataGrip (dim-6 dev access):** Drivers → add **Arrow Flight SQL JDBC** (Maven `org.apache.arrow:flight-sql-jdbc-driver:17.0.0`, class `org.apache.arrow.driver.jdbc.ArrowFlightJdbcDriver`). Data source URL:
  ```
  jdbc:arrow-flight-sql://mother:31337?useEncryption=false&user=weyland&password=weyland_dev_password
  ```
  No SSH tunnel/SSL (the NodePort is LAN-reachable; the app is plaintext — see security below). Creds are passed as **URL params** (the driver has no separate cred fields).
- **emit_duckdb (DataHub catalog):** the Dagster pod connects via ADBC Flight SQL (`grpc+tcp://gizmosql.data-mesh.svc:31337`) and catalogs the views (platform `duckdb`, lineage ← `parquet`). Runs in `datahub_catalog_emit_job`.

## Deploy

GitOps: `k8s/data-mesh/gizmosql.yaml` (Deployment + NodePort Service + `GizmosqlDown` PrometheusRule). The **secret is imperative** (carries the lakeFS keys + the init SQL — not in git):

```
kubectl -n data-mesh create secret generic gizmosql-secret --from-literal=GIZMOSQL_USERNAME=weyland --from-literal=GIZMOSQL_PASSWORD=weyland_dev_password --from-literal=INIT_SQL_COMMANDS="INSTALL httpfs; LOAD httpfs; CREATE SECRET lakefs (TYPE S3, KEY_ID '<lakefs-key>', SECRET '<lakefs-secret>', REGION 'us-east-1', ENDPOINT 'lakefs.data-mesh.svc.cluster.local:8000', URL_STYLE 'path', USE_SSL false); CREATE VIEW spotify_tracks AS SELECT * FROM read_parquet('s3://music/main/parquet/spotify_tracks/*.parquet', union_by_name=true); CREATE VIEW fma_tracks AS SELECT * FROM read_parquet('s3://music/main/parquet/fma_tracks/*.parquet', union_by_name=true); CREATE VIEW fma_genres AS SELECT * FROM read_parquet('s3://music/main/parquet/fma_genres/*.parquet', union_by_name=true); CREATE VIEW fma_echonest AS SELECT * FROM read_parquet('s3://music/main/parquet/fma_echonest/*.parquet', union_by_name=true);" --dry-run=client -o yaml | kubectl apply -f -
```

## Gotchas (every one cost us a cycle)

1. **`GIZMOSQL_PORT … not a valid integer` → CrashLoop.** k8s injects Docker-link service env vars (`GIZMOSQL_PORT=tcp://<ip>:31337`) for the same-named Service, colliding with GizmoSQL's own `GIZMOSQL_PORT` config var. Fix: **`enableServiceLinks: false`** on the pod.
2. **New pod can't schedule (Pending) after a fix.** The node runs ~98% CPU-committed, so a RollingUpdate double-books the CPU request and the new pod never schedules while the old (even crashing) one holds its slot. Fix: **`strategy: { type: Recreate }`** — kill old before new. (See [[k8s-rwo-recreate-strategy]].)
3. **`HTTP 400 … No region is provided`** reading the lake. DuckDB's S3 signature needs a region even against lakeFS. Add **`REGION 'us-east-1'`** to the `CREATE SECRET`.
4. **`schema mismatch in glob`** on `fma_echonest`/`fma_tracks`. Each transform run writes a *new* parquet file and FMA's flattened schema drifts run-to-run. Fix: **`read_parquet(..., union_by_name=true)`**. (Caveat: those dirs accumulate multiple runs' files → the views carry **duplicate rows**. Proper fix = the transform writing one deterministic file per table — B73/transform-cleanup.)
5. **`UNAVAILABLE: Network closed`** from the client. GizmoSQL **auto-generates a self-signed cert and serves TLS by default** (`grpc+tls://`). Either connect with TLS (and the client must skip verify), or run plaintext (below).

## Security model

- GizmoSQL runs **`TLS_ENABLED=0` (plaintext, `grpc+tcp://`)** and is **in the Istio mesh** (`sidecar.istio.io/inject: "true"`). The **in-cluster hop (emit_duckdb) is Istio mTLS** — so the ADBC client carries **no `TLS_SKIP_VERIFY`** (it was a flagged finding; resolved by the mesh, not papered over).
- **Open item (Phase 2):** the **external IDEA→NodePort hop is plaintext over the LAN** (password in the clear). The fix is a **gRPC-TLS ingress at `gizmosql.weyland.lab`** (Traefik terminates the real wildcard cert, forwards h2c into the mesh) → IDEA connects TLS with a valid cert, no skip-verify. Tracked in B69; low risk on a trusted home LAN, but it's the honest finish.

## Monitor

`GizmosqlDown` PrometheusRule (`kube_deployment_status_replicas_available{deployment="gizmosql"} == 0`, 5m → Alertmanager→Telegram). GizmoSQL exposes no `/metrics` and Flight SQL is gRPC (no HTTP page), so deployment-availability is the right signal; an optional Kuma **TCP** monitor on `mother:31337` is the shallow LAN ping.
