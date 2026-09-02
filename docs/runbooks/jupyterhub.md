# JupyterHub — the data-science notebook layer (B1.8 L8)

JupyterHub is the L8 notebook layer of the mesh: **per-user JupyterLab pods, on-demand**, spawned by KubeSpawner and
idle-culled to zero. The custom singleuser image ships the **datasets-lake toolkit** (polars / s3fs / pylance /
duckdb), so a notebook queries the mesh out of the box. Auth = Keycloak OIDC. Deployed via the **Zero-to-JupyterHub**
Helm chart as an Argo multi-source app; values `k8s/jupyterhub/jupyterhub-values.yaml`, image
`k8s/jupyterhub/singleuser/`. UI: `https://jupyter.weyland.lab`.

**Status: DEPLOYED 2026-07-12** — first build alongside the B79 node headroom. Hub+proxy always-on (tiny); singleuser
pods on-demand. Seed notebook `datasets_lake.ipynb` reads all 4 lakeFS silver formats + polars/DuckDB analysis. The
broader notebook **library** is [B81](../backlog.md) (maturity).

---

## 1. Architecture

```
browser ──► jupyter.weyland.lab (Traefik ingress + weyland-wildcard-tls)
                │
                ▼
          proxy (CHP) ──► hub (JupyterHub) ──OIDC──► Keycloak (weyland realm)
                                │  KubeSpawner (on-demand)
                                ▼
                       jupyter-<user>  (weyland-jupyter:local — polars/s3fs/pylance/duckdb)
                                │  egress (singleuser NetworkPolicy: privateIPs allowed)
                                ▼
                       lakeFS S3 gateway (data-mesh) · Trino · Cube · …the mesh
```

- **Chart:** Zero-to-JupyterHub, Argo app in `k8s/argocd/applications/helm-apps.yaml` (ns `jupyterhub`).
- **Auth:** Keycloak OIDC (`GenericOAuthenticator`), client `jupyterhub` codified in `tofu/keycloak/jupyterhub.tf`
  (CONFIDENTIAL; secret → k8s Secret `jupyterhub-oidc`). `allow_all: true` (solo lab). Callback
  `/hub/oauth_callback`.
- **Hub DB:** `sqlite-pvc` (first cut — no Postgres-mesh plumbing; migrate later if multi-user).
- **Singleuser:** custom image `weyland-jupyter:local` (built + `ctr import`ed into k3s, `pullPolicy: Never`); JupyterLab
  default; idle-cull after 1h; per-user 2Gi PVC; `LAKEFS_*` env from `lakefs-creds`.
- **On-demand tiering:** hub+proxy ~tiny always-on; notebook pods spawn per login, cull to zero.

---

## 2. Bring-up (reproducible)

1. **Keycloak client** (tofu lane) — creates the OIDC client + secret:
   ```
   cd tofu/keycloak && AWS_ACCESS_KEY_ID=admin AWS_SECRET_ACCESS_KEY=weyland_dev_password \
     TF_VAR_kc_admin_password=weyland_dev_password TF_VAR_operator_password=weyland_dev_password \
     tofu apply -target=keycloak_openid_client.jupyterhub
   tofu output -raw jupyterhub_client_secret
   ```
2. **Namespace + secrets** — the OIDC secret, the mkcert CA (back-channel to Keycloak), and the lakeFS creds:
   ```
   kubectl create ns jupyterhub --dry-run=client -o yaml | kubectl apply -f -
   kubectl -n jupyterhub create secret generic jupyterhub-oidc --from-literal=client_secret='<secret>'
   kubectl -n weyland get secret weyland-mkcert-ca -o jsonpath='{.data.rootCA\.pem}' | base64 -d > /tmp/rootCA.pem \
     && kubectl -n jupyterhub create secret generic weyland-mkcert-ca --from-file=rootCA.pem=/tmp/rootCA.pem
   K=$(kubectl -n data-mesh get secret lakefs-creds -o jsonpath='{.data.LAKEFS_ACCESS_KEY_ID}' | base64 -d)
   S=$(kubectl -n data-mesh get secret lakefs-creds -o jsonpath='{.data.LAKEFS_SECRET_ACCESS_KEY}' | base64 -d)
   kubectl -n jupyterhub create secret generic lakefs-creds \
     --from-literal=LAKEFS_ACCESS_KEY_ID="$K" --from-literal=LAKEFS_SECRET_ACCESS_KEY="$S"
   ```
   (These secrets are NOT in git — recreate on a fresh cluster.)
3. **Custom singleuser image** — build on mother + import into k3s (single node → no registry):
   ```
   rsync ... k8s/jupyterhub/singleuser/ emangini@mother:~/jupyter-singleuser/
   docker build -t weyland-jupyter:local ~/jupyter-singleuser/ && docker save weyland-jupyter:local | sudo ctr -n k8s.io images import -
   ```
4. **Push** `jupyterhub-values.yaml` + the Argo app → Argo deploys the chart.

---

## 3. Gotchas (all hit during bring-up — read before touching)

- **OIDC back-channel needs the mkcert CA.** The hub's SERVER-SIDE token/userinfo calls to `keycloak.weyland.lab`
  use the mkcert cert; libcurl won't trust it → `HTTP 599 SSL certificate problem` → **500 on `/hub/oauth_callback`**.
  Fix: mount `weyland-mkcert-ca` + `c.GenericOAuthenticator.http_request_kwargs = {"ca_certs": "/etc/mkcert/rootCA.pem"}`
  (in `hub.extraConfig`). Same pattern as Grafana/GlitchTip/DataHub.
- **Node pod-cap.** The lab hit the **k3s default 110-pods-per-node** cap (`FailedScheduling: Too many pods`) — raised
  to **250** via `/etc/rancher/k3s/config.yaml` (`kubelet-arg: ["max-pods=250"]`) + `systemctl restart k3s` (control
  plane restart; containerd keeps running containers, so far lighter than a VM reboot). Also disabled the Z2JH
  `prePuller` (hook + continuous-image-puller = extra pod slots).
- **Singleuser NetworkPolicy blocks the mesh.** Z2JH ships a default NetworkPolicy on `component=singleuser-server`
  pods that **blocks egress to private cluster IPs** (security default) — so notebooks got `Connection refused` to
  `lakefs.data-mesh:8000` even though an ad-hoc pod in the same ns reached it fine. Fix:
  `singleuser.networkPolicy.egressAllowRules.privateIPs: true` (the cloud-metadata block stays).
- **Custom image = `ctr import` + `pullPolicy: Never`.** Single-node k3s → build on mother, `docker save | ctr -n
  k8s.io images import -`, reference `weyland-jupyter:local`. If a spawn shows `ErrImageNeverPull`, the import didn't land.
- **The PVC hides baked notebooks → git-sync on spawn (B81).** The user PVC mounts at `/home/jovyan`, hiding anything
  baked there. The `lifecycleHooks.postStart` populates `~/notebooks` on every spawn: first `cp -rn /opt/examples/.`
  (the baked copy, no-clobber → offline fallback), then a shallow **sparse `git clone`** of `singleuser/notebooks/`
  from the public repo, `cp -rf` over the top (library == `main`). git is in the scipy base, so growing the library is
  a `git push`, **not an image rebuild**. Reachable because the singleuser NetworkPolicy allows public egress
  (`0.0.0.0/0` except the private ranges + cloud-metadata) — GitHub is public, the mesh is the re-allowed private ranges.
- **Editing a live notebook fights `kubectl cp`.** An OPEN notebook autosaves its in-memory copy back over a `kubectl
  cp`. Sequence: **close the tab (File → Close and Shutdown) → cp → reopen**. (Moot once the image bakes the notebook;
  B81's git-sync makes library updates a non-event.)
- **s3fs vs object_store creds keys.** polars' Rust readers (parquet/lance) take `access_key_id`/`secret_access_key`;
  its S3 IPC path (arrow) routes through aiobotocore wanting `aws_*` → read arrow/avro bytes via `s3fs` then parse
  locally instead. DuckDB httpfs needs `SET s3_region='us-east-1'` (400 "No region" otherwise).

---

## 4. The notebook library (B81)

Notebooks live in `k8s/jupyterhub/singleuser/notebooks/` (git-synced into `~/notebooks` — see §3) with a
`README.md` index. Each must **run end-to-end** — that IS the test (DoD); the per-format set is self-contained,
the stack-layer set runs against the live mesh. Validate by `jupyter nbconvert --to notebook --execute`.

- **`datasets_lake.ipynb`** (seed) — reads the **music** silver in all 4 lakeFS formats, then polars analysis + DuckDB
  SQL + matplotlib. Env `LAKEFS_ENDPOINT` / `LAKEFS_ACCESS_KEY_ID` / `LAKEFS_SECRET_ACCESS_KEY` is injected.
- **Per-format deep dives (shipped 2026-09-01, all self-contained, headless-execute clean):** `01_format_parquet`
  (row groups, encodings, compression, projection + pushdown) · `02_format_arrow_ipc` (zero-copy interop, IPC file vs
  stream, mmap) · `03_format_avro` (schema evolution, codecs) · `04_format_lance` (versioning/time-travel, random
  access, real IVF_PQ vector index + ANN).
- **Storage & versioning (shipped 2026-09-01, both validated live, headless-execute clean):** `10_storage_lakefs`
  (git-for-data over the `music` repo — zero-copy branch/commit/diff/merge/log + commit-id time-travel, scratch-branch
  only, self-cleaning) · `11_storage_nessie_iceberg` (table-level versioning — Iceberg snapshots/schema-evolution/atomic
  commits + Nessie git-like catalog branching + commit-hash time-travel via `StaticTable`; reads `dbt.mart_*`
  read-only, writes a scratch `nb_demo` namespace, self-cleaning). One versions objects, the other tables — they stack.
  **Iceberg creds:** the singleuser pod injects `ICEBERG_S3_ACCESS_KEY`/`ICEBERG_S3_SECRET_KEY` from SealedSecret
  `jupyterhub/iceberg-s3-creds` (mirrors data-mesh `nessie-secret` s3 keys); all other Nessie/warehouse URLs default to
  the cluster service addresses in the notebook. Gotcha: Nessie **vends** the S3 endpoint+creds per table (overrides the
  client `s3.endpoint`), and versions at the catalog-commit level — a single live Iceberg snapshot per table — so
  snapshot-id time-travel fails; time-travel is done by Nessie commit hash + `StaticTable` instead.
- **Query & federation (started 2026-09-01, validated live, headless-execute clean):** `20_query_trino_federation`
  (Trino federated SQL — catalog/schema discovery, a real cross-catalog join `iceberg.eval.eval_scores` ⋈
  `postgresql.public.eval_results` in one query, predicate + column pushdown via `EXPLAIN`; read-only, env-driven
  `TRINO_HOST`/`TRINO_PORT`/`TRINO_USER` defaulting to the in-cluster coordinator, `%pip install trino` since the
  client isn't baked). **Catalog reality:** only `iceberg` (Nessie/Iceberg lakehouse) + `postgresql` (operational
  eval/operator DB) + `system` are wired as Trino catalogs — the Tier-2 stores are NOT Trino connectors, they get
  native clients in `22`. Trino here is UNMESHED (single `trino` container, no istio sidecar), so the singleuser pod
  reaches it over plain HTTP via the privateIPs NetworkPolicy — no mTLS wall. `22` (Tier-2 native) still to come.
- **`21_query_duckdb_gizmosql` (2026-09-01, validated live, headless-execute clean):** DuckDB two ways —
  **embedded** (in the kernel, httpfs over the lakeFS S3 gateway, window fns + projection pushdown, and true
  zero-copy Arrow interop proven by identical buffer address across polars/arrow/duckdb) using the EXISTING
  `lakefs-creds`; and **served** via GizmoSQL (Arrow Flight SQL, ADBC client `%pip install adbc-driver-flightsql`)
  over the persisted silver base tables (`datasets_music`/`datasets_health`, USDA relational JOINs). Read-only.
  GizmoSQL reachable from rogueone at the NodePort `192.168.1.243:31337` (DataGrip path); in-cluster default
  `grpc+tcp://gizmosql.data-mesh.svc:31337`, plaintext (Istio mTLS covers the hop). **Served half needs creds:**
  the singleuser pod gets `GIZMOSQL_USERNAME`/`GIZMOSQL_PASSWORD` from SealedSecret `jupyterhub/gizmosql-creds`
  (mirrors data-mesh `gizmosql-secret`); the embedded half needs no creds beyond `LAKEFS_*`.
- **`22_query_tier2_native` (2026-09-01, validated live, headless-execute clean) — completes the query wave:** the
  six Tier-2 stores by NATIVE client (they are NOT Trino connectors) — ClickHouse (`clickhouse-connect`) · Cassandra
  (`cassandra-driver`) · MongoDB (`pymongo`) · CockroachDB (`psycopg`, insecure dev mode) · TimescaleDB (`psycopg`,
  hypertables) · MySQL (`PyMySQL`), each a real read on hydrated music/health data. Env-driven, in-cluster DNS
  defaults; the four password stores share `TIER2_DB_PASSWORD` (SealedSecret `jupyterhub/tier2-creds`), Cassandra +
  Cockroach need none. **Reach from rogueone = the new `-lan` NodePorts** (`k8s/data-mesh/tier2-lan.yaml`:
  clickhouse 30123 · cassandra 30942 · mongodb 30017 · cockroachdb 30257 · timescaledb 30543 · mysql 30306) — the
  lab is NodePorts-only, never `kubectl port-forward`. **Mesh caveat (in-pod UAT):** `data-mesh` is istio-injected;
  cassandra opts out (`inject:false`), mysql/timescale opt in (`inject:true`), the rest inherit the ns default — so
  a store IS meshed once its pod restarts, and a plaintext client (an unmeshed singleuser pod) then can't reach it.
  The notebook was validated from INSIDE the mesh (the real in-cluster environment); for the actual spawn to reach
  the meshed stores (MySQL here, GizmoSQL in `21`) the singleuser pod must be mesh-joined — track that in the UAT.
- **Vector & graph (2026-09-01, all four validated live, headless-execute clean):** `30_vector_qdrant` (served
  vector DB — semantic ANN seeded from a stored vector, payload-filtered search, HNSW/quantization tuning over
  `weyland_chunks`/dataset collections) · `31_vector_weaviate` (**the U16 deliverable** — class/object browse, vector
  + BM25 + hybrid + raw GraphQL; needs both HTTP `30087` and gRPC `32418` NodePorts) · `32_vector_lancedb` (embedded
  — opens the lakeFS-backed Lance tables via object-store `storage_options`, IVF_PQ ANN vs exact cosine; reuses
  `LAKEFS_*`) · `33_graph_neo4j` (Cypher schema discovery + multi-hop traversal + degree/co-listen aggregation; GDS
  detected-and-skipped on Community edition). Qdrant open, Weaviate anonymous, LanceDB via lakeFS creds; only Neo4j
  needs a secret — `NEO4J_PASSWORD` from SealedSecret `jupyterhub/neo4j-creds` (mirrors weyland `neo4j-secret`). All
  four unmeshed, reached from rogueone via their existing NodePorts (qdrant 30083 · weaviate 30087/32418 · neo4j
  bolt 30086 · lakeFS 30800). **U16 (Weaviate UI) is satisfied by `31`.**
- **Transform & semantic (2026-09-02, both validated live IN-CLUSTER, headless-execute clean):**
  `40_transform_dbt_marts` (the dbt transform tier — query the 7 `iceberg.dbt.*` marts via Trino + the MetricFlow
  semantic models: metric definitions + the compiled-equivalent Trino query; the real dbt project is two-layer
  staging→marts, no intermediate) · `41_semantic_cube` (Cube headless semantic layer via its pg-wire SQL API, the
  `MEASURE()` contract, governed measures over the marts). **Validated in-cluster** (ephemeral injected data-mesh
  pod) because Trino + Cube are ClusterIP-only — NOT via NodePort (a Trino NodePort would expose the no-auth engine
  on the LAN) and NOT via port-forward. Trino needs no creds; Cube SQL API needs `CUBE_SQL_PASSWORD` from
  SealedSecret `jupyterhub/cube-creds` (mirrors data-mesh `cube-secret` `CUBEJS_SQL_PASSWORD`).
- **Feature & ML (2026-09-02, both validated live, headless-execute clean):** `50_feature_feast` (Feast train/serve
  parity — online retrieval from Valkey + historical point-in-time from Postgres over `track_audio_features` /
  `state_health_risk`; validated IN-CLUSTER since weyland-postgres is STRICT-mTLS; needs `WEYLAND_PG_PASSWORD`) ·
  `51_ml_mlflow` (MLflow tracking + registry — experiments/runs/metrics, the `genre_classifier` registry v1-v9,
  guarded load+predict; Ray covered as the genre-trainer pattern with its 247 Ray-Tune runs; NodePort 30500,
  needs `MLFLOW_TRACKING_USERNAME`/`PASSWORD`). Both creds in one SealedSecret `jupyterhub/mlplat-creds`
  (`WEYLAND_PG_PASSWORD` ← weyland-postgres-secret; MLflow basic-auth admin/dev-password). Note: the MLflow
  model-LOAD cell degrades to a note in-pod unless the `mlflow`-bucket S3 artifact creds are also injected —
  metadata browsing works regardless; a future enhancement if live model-load in-pod is wanted.
- **AI & RAG (2026-09-02, all three validated live, headless-execute clean):** `60_rag_llamaindex` (end-to-end RAG —
  local bge-base query embed [NO prefix — matches the corpus's bare+normalized ingest, verified against the real
  retrievers], retrieve `weyland_chunks` from Qdrant, generate via LiteLLM `wl-rag`; grounded-vs-no-context contrast;
  explicit qdrant-client+openai path, not llama-index, because the corpus stores text under `content`) ·
  `61_gateway_litellm` (LiteLLM OpenAI-compat gateway — `wl-*` aliases, chat+streaming, live routing incl. the
  underlying provider/model/latency) · `62_eval_rag` (RAG eval leaderboard via Trino over `iceberg.eval` +
  `postgresql` + one faithfulness score judged LIVE via `wl-judge`, mirroring `eval_scores.py`). 60/61 validated from
  rogueone via NodePort (Qdrant 30083, LiteLLM 30400); 62 validated IN-CLUSTER (Trino ClusterIP). Query embeddings
  run locally (bge-base, HF download cached under the PVC home); only new cred = `LITELLM_MASTER_KEY` from
  SealedSecret `jupyterhub/litellm-creds` (mirrors weyland `litellm-secrets`). Gotcha: in the `data-mesh` ns k8s
  auto-injects a colliding `TRINO_PORT=tcp://...` service var — the validation run overrides `TRINO_HOST`/`TRINO_PORT`;
  the real singleuser pods aren't in data-mesh so the committed in-cluster defaults are correct.
- **Stack-layer waves (next):** governance/quality (DataHub · Soda · Ranger) · streaming (Redpanda · Debezium) — one
  per layer, against live services. See `docs/backlog.md` → B81 (EMA-71).

See [[cube-semantic-layer-b1.7]], [runbooks/cube.md](cube.md).
