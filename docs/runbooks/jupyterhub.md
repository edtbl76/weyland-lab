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
                       jupyter-<user>  (registry.weyland.lab/weyland-jupyter — polars/s3fs/pylance/duckdb)
                                │  egress (singleuser NetworkPolicy: privateIPs allowed)
                                ▼
                       lakeFS S3 gateway (data-mesh) · Trino · Cube · …the mesh
```

- **Chart:** Zero-to-JupyterHub, Argo app in `k8s/argocd/applications/helm-apps.yaml` (ns `jupyterhub`).
- **Auth:** Keycloak OIDC (`GenericOAuthenticator`), client `jupyterhub` codified in `tofu/keycloak/jupyterhub.tf`
  (CONFIDENTIAL; secret → k8s Secret `jupyterhub-oidc`). `allow_all: true` (solo lab). Callback
  `/hub/oauth_callback`.
- **Hub DB:** `sqlite-pvc` (first cut — no Postgres-mesh plumbing; migrate later if multi-user).
- **Singleuser:** custom image `registry.weyland.lab/weyland-jupyter:<tag>` (in-cluster registry, `pullPolicy: IfNotPresent` — prune-safe, see §3); JupyterLab
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
3. **Custom singleuser image** — build on mother + push to the in-cluster registry (NOT ctr-import — see the prune
   gotcha in §3). Rebuild = bump the tag in `jupyterhub-values.yaml` (`singleuser.image.tag`) and:
   ```
   rsync -a --delete k8s/jupyterhub/singleuser/ emangini@mother:~/jupyter-singleuser/
   docker build -t registry.weyland.lab/weyland-jupyter:<tag> ~/jupyter-singleuser/ && docker push registry.weyland.lab/weyland-jupyter:<tag>
   ```
   (`pullPolicy: IfNotPresent`, no imagePullSecret — the node has registry access. If `docker push` 401s,
   `docker login registry.weyland.lab` first; if a large layer 499s, that's the Traefik `readTimeout` — see
   [[traefik-readtimeout-registry-push]].)
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
- **Custom image = in-cluster registry + `pullPolicy: IfNotPresent` (NOT ctr-import).** The image was originally
  ctr-imported as `weyland-jupyter:local` / `pullPolicy: Never`, but the weekly `weyland-image-prune`
  (`k3s crictl rmi --prune`) removes UNUSED images — and a scale-to-zero singleuser image reads as unused, so it got
  pruned and the next spawn died with **`ErrImageNeverPull`** (hit 2026-09-02, mid-UAT). Fix: push to
  `registry.weyland.lab/weyland-jupyter:<tag>` + `IfNotPresent`, so a prune just triggers a re-pull. If a spawn still
  shows `ErrImageNeverPull`, the tag in values doesn't exist in the registry (build+push it) — it is no longer a
  ctr-import problem.
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
- **Governance & quality (2026-09-02, all three validated live IN-CLUSTER, headless-execute clean):**
  `70_governance_datahub` (DataHub catalog — search, schema/owners/tags/domain, bidirectional lineage, domains +
  glossary, via the acryl-datahub SDK GraphQL; needs `DATAHUB_TOKEN`) · `71_quality_soda` (Soda contract scan over
  the marts via `trino-noauth`, 8/8 checks with measured values, fail-closed guard against a false "0 checks passed";
  ships `setuptools<81` [distutils on py3.12] + `auth_type: NoAuthentication` [newer trino client refuses BasicAuth
  over http] fixes — the committed dagster `soda/configuration.yml` predates the latter) · `72_authz_ranger` (Ranger
  column mask on the main Trino — `mask-depression-pct-analyst` MASK_NULL: `analyst` sees `mart_state_health_trends.
  depression_pct` NULL, `dbt` sees real, sibling cols unchanged; DEFAULT-DENY + `trino-noauth` bypass explained).
  Only DataHub needs a secret — `jupyterhub/datahub-creds` (← weyland `datahub-token`); Soda uses trino-noauth,
  Ranger sets the Trino user via the client (no password).
- **Streaming (2026-09-02, both validated live IN-CLUSTER, headless-execute clean) — the FINAL wave:**
  `80_streaming_redpanda` (Kafka API + Schema Registry — list topics, inspect a registered Avro schema, consume a
  bounded Avro batch with live offset watermarks via `confluent-kafka[avro]`, fresh read-only consumer group) ·
  `81_streaming_cdc_debezium` (Debezium CDC — connector status via Kafka Connect :8083, consume
  `cdc.musicbrainz.public.cdc_demo` Debezium-Envelope change events, and the Iceberg mirror
  `iceberg.datasets_music.cdc_demo_live` via Trino — the CDC→lakehouse loop). No creds (Redpanda is plaintext,
  unmeshed, in-cluster). Note: nb 81's live consume showed 0 events because the demo topic's 7-day retention aged out
  the historical records and there is no periodic writer — the notebook proves the decode path against the real
  registered schema and shows the populated Iceberg mirror instead of fabricating events; to see a live envelope an
  operator would write one row to `musicbrainz.public.cdc_demo`.
- **B81 NOTEBOOK LIBRARY COMPLETE (2026-09-02):** 25 numbered notebooks + the `datasets_lake` seed, spanning
  formats → storage → query → vector/graph → transform/semantic → feature/ML → AI/RAG → governance/quality →
  streaming, each validated end-to-end against the live mesh. Distribution is git-sync (§3). **Remaining: the operator
  spawn-verify UAT only** — spawn JupyterHub (Keycloak login), confirm `~/notebooks` git-syncs and the notebooks run
  in-pod (the singleuser pod is mesh-joined for the meshed stores).
- **DECISION (2026-09-02): nb 51's MLflow model-LOAD cell is left as a graceful note in-pod — NOT wired for live
  load.** Loading the registered model blob from `s3://mlflow/` needs MinIO artifact creds, which MLflow/boto3 read
  as GENERIC `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`. Injecting those into the singleuser pod would leak into
  every notebook kernel's default credential chain (collision) and widen every spawn's blast radius to the mlflow
  MinIO bucket — for one cell whose surrounding value (experiments/runs/registry browse) already works in-pod. So it
  stays a note. If live in-pod model load is ever wanted, do it SCOPED (not global env): a dedicated `mlflow-s3-creds`
  SealedSecret injected as `MLFLOW_S3_ACCESS_KEY`/`_SECRET`/`_ENDPOINT`, and nb 51's load cell sets `AWS_*` from those
  only inside that cell. Not worth the operator round-trip today.
- **nb 81 CDC (2026-09-02): the consume cell shows a real live `op=u` envelope** (id 11 `bravo-v2`→`bravo-v3`),
  produced by a one-row UPDATE to `musicbrainz_db.public.cdc_demo` (the purpose-built demo table; the topic had aged
  out its 7-day retention). To refresh the demo again, UPDATE a `cdc_demo` row and re-run the notebook.

---

## 5. Operator spawn-verify UAT (B81) — the final gate

Everything below the notebooks was validated out-of-pod (NodePort from rogueone, or an ephemeral in-cluster pod).
This UAT is the ONLY remaining B81 item: prove the same holds **inside a real singleuser pod** — git-sync
distribution, the mesh-join (for meshed stores), and every injected credential. Operator-only (browser + Keycloak
SSO; a bot can't spawn). Tick each box; a notebook "passes" = **Run All Cells → 0 error outputs**.

### 5.0 Pre-flight (from mother/kubectl, before spawning)
- [ ] All eight jupyterhub creds exist: `kubectl -n jupyterhub get secret jupyterhub-oidc lakefs-creds iceberg-s3-creds gizmosql-creds tier2-creds neo4j-creds cube-creds mlplat-creds litellm-creds datahub-creds` (10 incl. oidc+lakefs) all present.
- [ ] Argo `jupyterhub` app is **Synced/Healthy** (the latest `jupyterhub-values.yaml` with `extraLabels` + all `extraEnv` is live).
- [ ] The six data-mesh `-lan` NodePorts + the Tier-2/vector stores are up (only needed if you also spot-check from rogueone; the in-pod path uses ClusterIP DNS).

### 5.1 Spawn + distribution
- [ ] Browse `https://jupyter.weyland.lab` → Keycloak login → spawn a server (first spawn pulls `registry.weyland.lab/weyland-jupyter:<tag>` from the in-cluster registry — a few seconds).
- [ ] **Sidecar confirmed** (the mesh-join): `kubectl -n jupyterhub get pod -l component=singleuser-server -o jsonpath='{.items[0].spec.containers[*].name}'` shows **`istio-proxy`** alongside `notebook`. (If not, meshed-store cells in 21/22/41 will hang — check the `extraLabels` landed.)
- [ ] **git-sync worked**: in a terminal, `ls ~/notebooks` shows all 25 numbered notebooks + `datasets_lake.ipynb` + `README.md`. The `postStart` log (`kubectl -n jupyterhub logs <pod> -c notebook` or the pod events) shows "notebook library git-synced".
- [ ] **Scratch survives**: create `~/scratch/keep.txt`; it persists across a cull/respawn (PVC), while edits inside `~/notebooks` are overwritten on respawn (git == source). (Optional, confirms the distribution contract.)

### 5.2 Per-notebook run — Run All Cells, expect 0 errors

**Fastest way — run the whole library headless from the JupyterLab terminal** (inside the pod, so it has the
injected env + in-cluster DNS + can `%pip`), one PASS/FAIL line per notebook instead of clicking 26 times:
```
cd ~/notebooks && for nb in $(ls [0-9]*.ipynb datasets_lake.ipynb 2>/dev/null); do jupyter nbconvert --to notebook --execute --stdout "$nb" >/dev/null 2>&1 && echo "PASS  $nb" || echo "FAIL  $nb"; done
```
`--stdout >/dev/null` runs without modifying the files; a cell error makes nbconvert exit non-zero → `FAIL`. Takes
several minutes (some notebooks `%pip install` per run; `60` downloads bge-base ~440MB once). **Expected: all PASS**,
incl. `51_ml_mlflow` (its model-load cell catches the missing artifact creds and prints a note, so it doesn't error).
For any `FAIL`, get the traceback with `jupyter nbconvert --to notebook --execute --stdout <nb> 2>&1 | tail -40`. This
IS the in-pod test — a `FAIL` on `21`/`22`/`41` means the mesh-join regressed, on `60` means git-sync/egress, on a
creds notebook means its sealed secret is missing. Tick the per-notebook boxes below from the PASS/FAIL run.

Formats (self-contained, no external creds):
- [ ] `01_format_parquet` · `02_format_arrow_ipc` · `03_format_avro` · `04_format_lance` — all execute; `04` builds a real IVF_PQ index.

Storage (needs `lakefs-creds`, `iceberg-s3-creds`):
- [ ] `10_storage_lakefs` — branch/commit/diff/merge over the `music` repo; **cleanup cell leaves only `main`** (assert passes).
- [ ] `11_storage_nessie_iceberg` — reads `dbt.mart_*`; scratch `nb_demo` namespace created + **dropped** (cleanup asserts pass).

Query:
- [ ] `20_query_trino_federation` — the `iceberg.eval ⋈ postgresql` join returns rows.
- [ ] `21_query_duckdb_gizmosql` — **MESHED-STORE CHECK**: the GizmoSQL (served) half connects over mTLS; embedded DuckDB over lakeFS works.
- [ ] `22_query_tier2_native` — **MESHED-STORE CHECK**: all six stores; **MySQL** is the one that only works if the sidecar is present (needs `tier2-creds`).

Vector/graph (Qdrant/Weaviate open; `33` needs `neo4j-creds`):
- [ ] `30_vector_qdrant` — `weyland_chunks` search (768-dim, ~8300 pts).
- [ ] `31_vector_weaviate` — vector/BM25/hybrid/GraphQL (the U16 deliverable).
- [ ] `32_vector_lancedb` — opens the lakeFS-backed Lance tables (reuses `lakefs-creds`).
- [ ] `33_graph_neo4j` — Cypher traversal over the 634k-node graph (needs `neo4j-creds`).

Transform/semantic:
- [ ] `40_transform_dbt_marts` — the 7 marts via Trino + a MetricFlow metric.
- [ ] `41_semantic_cube` — **MESHED-STORE CHECK**: Cube SQL API (`MEASURE()`), needs `cube-creds`.

Feature/ML (needs `mlplat-creds`):
- [ ] `50_feature_feast` — online (Valkey) + historical PIT (Postgres) retrieval; needs `WEYLAND_PG_PASSWORD`.
- [ ] `51_ml_mlflow` — experiments/runs/registry browse works; **KNOWN GAP: the model-LOAD cell shows a graceful note** (S3 artifact creds deliberately not injected — see §4). That note is a PASS, not a failure.

AI/RAG (needs `litellm-creds`; `60` downloads bge-base from HF on first run):
- [ ] `60_rag_llamaindex` — **GIT-SYNC/EGRESS CHECK**: `%pip install` + the HF bge-base download must succeed (public egress); retrieval returns on-topic chunks; grounded answer via `wl-rag`.
- [ ] `61_gateway_litellm` — `wl-*` aliases list + a chat + streaming.
- [ ] `62_eval_rag` — the eval leaderboard + a live `wl-judge` faithfulness score.

Governance/quality (`70` needs `datahub-creds`; 71/72 no creds):
- [ ] `70_governance_datahub` — search + lineage (needs `DATAHUB_TOKEN`).
- [ ] `71_quality_soda` — a contract scan over the marts (8/8 pass) via `trino-noauth`.
- [ ] `72_authz_ranger` — **MESHED?** no (main Trino unmeshed) — column mask: as `analyst` `depression_pct` is NULL, as `dbt` real.

Streaming (no creds):
- [ ] `80_streaming_redpanda` — list topics + consume an Avro batch.
- [ ] `81_streaming_cdc_debezium` — connector RUNNING + the live `op=u` (`bravo-v2`→`bravo-v3`) + mirror `bravo-v3`.

### 5.3 Sign-off
- [ ] Every notebook above ran with **0 error outputs** in-pod (nb 51 model-load note excepted, by design).
- [ ] The three meshed-store checks (21 GizmoSQL, 22 MySQL, 41 Cube) succeeded → the singleuser mesh-join is confirmed working.
- [ ] The RAG egress check (60) succeeded → git-sync + public `%pip`/HF egress confirmed.
- [ ] Record the run (date + any deviation) here, flip **B81/EMA-71 → Done**, and mark the DoD demo pillar for the notebook library.

> If a meshed-store cell (21/22/41) hangs: the sidecar didn't inject — re-check §5.1's sidecar box and the
> `singleuser.extraLabels` in values. If a creds cell fails: the matching sealed secret isn't in the jupyterhub ns
> (§5.0). If git-sync didn't populate `~/notebooks`: check the `postStart` log + the singleuser NetworkPolicy egress.

---

## 6. Operational completeness (DoD Pillar 6) — the accepted state

- **Reproducible from git:** singleuser image on `registry.weyland.lab` (`IfNotPresent`, not `:local`/ctr-import), Argo-onboarded Helm values, notebooks git-synced, no un-codified config. (This is what the 2026-09-02 prune incident fixed.)
- **Secrets restorable:** all ten `jupyterhub`-ns secrets are SealedSecrets in git (`jupyterhub-oidc`, `lakefs-creds`, `iceberg-s3-creds`, `gizmosql-creds`, `tier2-creds`, `neo4j-creds`, `cube-creds`, `mlplat-creds`, `litellm-creds`, `datahub-creds`).
- **Monitored + alerted:** liveness via the **blackbox probe** on `jupyter.weyland.lab` (synthetic 1:1) + the blackbox `probe_success` down-alert → Telegram. **Metrics scrape is a deliberate accepted gap:** the Z2JH hub's `/hub/metrics` is not exposed for scrape (no `authenticate_prometheus` config) and there is no ServiceMonitor/dashboard — for a solo, on-demand (scale-to-zero, single-user) notebook hub the internal spawn/active-user metrics are low value, and blackbox already answers "is it up." No scraped `job` exists, so the servicemonitor/dashboard coverage guards do not flag it. Revisit only if JupyterHub becomes multi-user.
- **Backed up:** the hub `sqlite-pvc` holds recreatable state (user list/tokens — re-derived from Keycloak); per-user home PVCs hold scratch only (the library is git-synced, reproducible). No backup by design — state, not data.
- **Triggered:** the notebook library refreshes by git-sync on every spawn (freshness = a `git push`), not a timer — nothing to schedule.

See [[cube-semantic-layer-b1.7]], [runbooks/cube.md](cube.md), [demos/jupyter-notebook-library.md](../demos/jupyter-notebook-library.md), [diagrams/flow-jupyter-notebook-library.md](../diagrams/flow-jupyter-notebook-library.md).
