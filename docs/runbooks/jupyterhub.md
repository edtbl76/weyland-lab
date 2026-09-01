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
- **Stack-layer waves (next):** storage/query/vector/transform/ML/RAG/governance/streaming — one per layer, against
  live services, incl. the folded-in Weaviate notebook (U16). See `docs/backlog.md` → B81 (EMA-71).

See [[cube-semantic-layer-b1.7]], [runbooks/cube.md](cube.md).
