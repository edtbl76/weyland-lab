# Runbook — Remote model training on rogueone (registry → trainer → MLflow)

The platform's **remote training capability**: heavy model training runs on **rogueone** (ThinkPad P16 — 128 GB
RAM, 32 cores, RTX 5000 Ada), while weyland stays the **platform** (MLflow tracking + registry, MinIO artifacts,
lakeFS silver). A training job is a **self-contained container**, stored in a **MinIO-backed OCI registry**,
that rogueone pulls, runs to completion, and discards.

First consumer: the **genre classifier** (`services/genre-trainer/`). But the pattern is generic — any GPU/CPU
training job that needs more muscle than the k3s cluster follows the same path. This is the "capacity we figure
out to run remotely" half of the B1.8 data-science tier (the JupyterHub/Ray build proper is still deferred; this
is the pragmatic, single-container version of the same idea).

> **Why not just run it in-cluster?** The dagster pod is 1Gi and the k3s box is 32 GB; training belongs on the
> box with the RAM + GPU. weyland is the control plane, rogueone is the compute. (This RandomForest is CPU-bound
> and won't touch the Ada — the GPU payoff comes when the trainer is a GPU framework over the same path.)

---

## Architecture

```
  rogueone (Docker Desktop)                          weyland k3s cluster (mother, 192.168.1.243)
  ┌───────────────────────────────┐                 ┌──────────────────────────────────────────────┐
  │  docker run genre-trainer      │   pull image    │  registry.weyland.lab  ──S3──▶  MinIO         │
  │    ├─ entrypoint.sh            │◀────────────────┤  (distribution/registry, blobs in MinIO)      │
  │    │   via mounted kubeconfig: │                 │                                                │
  │    │   1. kubectl get secret ──┼───── API 6443 ─▶│  Secrets: lakefs-creds, aidlc-kb-minio-secret │
  │    │   2. kubectl port-forward─┼───── API 6443 ─▶│  svc/mlflow(5000) svc/minio(9000) svc/lakefs  │
  │    │      → container localhost │                 │                                    (8000)      │
  │    └─ train_genre.py           │                 │                                                │
  │        read silver  ───────────┼── localhost:8000 (fwd) ─▶  lakeFS gateway ──▶ music/…/spotify   │
  │        fit RandomForest (32c)  │                 │                                                │
  │        log params/metrics  ────┼── localhost:5000 (fwd) ─▶  MLflow server ──▶ Postgres (metadata)│
  │        log_model  ─────────────┼── localhost:9000 (fwd) ─▶  MinIO  s3://mlflow/…  (ARTIFACT)     │
  └───────────────────────────────┘                 └──────────────────────────────────────────────┘
```

The container is handed **only a kubeconfig**. Everything else — creds, service reachability — it derives from
that. No secrets on the command line, no host port-forwards, no ingress/SSO in the path.

---

## The MinIO-backed registry

`registry.weyland.lab` — a `distribution/registry` (`registry:2.8.3`) whose blobs live in a MinIO bucket
(`registry`), so the pod is **stateless** (no PVC). Manifest: `k8s/registry/registry.yaml`; Argo app in
`k8s/argocd/applications/subdir-apps.yaml`. Reusable platform-wide (this is the in-cluster registry B57 wanted).

Bring-up (once):
```
# bucket (throwaway mc pod, creds from the minio secret):
U=$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d); P=$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d); kubectl -n minio run mc-mkbucket-registry --rm -i --restart=Never --image=minio/mc --env="MC_HOST_m=http://$U:$P@minio.minio.svc.cluster.local:9000" -- mb -p m/registry
# then push k8s/registry/ + the subdir-apps.yaml entry → Argo deploys it.
```

**No auth** — LAN-only registry on a trusted LAN; open push/pull is the frictionless choice, consistent with the
other dev-only LAN surfaces. DNS: add `registry.weyland.lab` to the LAN DNS / rogueone `/etc/hosts` if there's no
wildcard.

### Registry gotchas

- **`REGISTRY_STORAGE_REDIRECT_DISABLE: "true"`** — the key is `storage.redirect.disable` (a sibling of `s3`),
  so the env var is `REGISTRY_STORAGE_REDIRECT_DISABLE`, **not** `..._S3_REDIRECT_DISABLE`. Without it the
  registry redirects blob GETs to *presigned MinIO URLs* at `minio.minio.svc:9000` that external clients
  (rogueone) can't reach → `pull` fails mid-layer. Disabling redirect makes the registry proxy blob bytes
  through the ingress.
- **No web UI** — a Docker registry is an API. `https://registry.weyland.lab/` is a blank 200; browse via
  `/v2/_catalog`, the docker CLI, or IntelliJ.
- **IntelliJ Docker Registry** — type **Generic**, address `registry.weyland.lab`. With Traefik basic-auth it
  reported *"Unsupported registry"* (Traefik's 401 lacks the `Docker-Distribution-Api-Version` header IntelliJ
  sniffs) — dropping auth fixed it. The Generic connector still insists on a non-empty username/password, so
  enter a throwaway (`anonymous` / `x`) — the no-auth registry discards them.

---

## The two-plane MLflow split (why the upload finally worked)

The MLflow server runs with `--serve-artifacts --artifacts-destination s3://mlflow/`, which **proxies artifact
uploads through the server** (client → server → boto3 → MinIO). For a multi-GB `model.pkl` that proxy hop —
through the 1Gi, meshed MLflow pod — **times out** (gunicorn `WORKER TIMEOUT`, the whole session's original bug).

Fix: split the planes.

| Plane | Route | Config |
|---|---|---|
| **metadata** (params, metrics, registry entry) | through the MLflow server → Postgres | `MLFLOW_TRACKING_URI` |
| **artifact** (`model.pkl`) | client → **MinIO, direct** | experiment `artifact_location = s3://mlflow/<name>` + client `MLFLOW_S3_ENDPOINT_URL`/`AWS_*` |

The trainer's `ensure_experiment` creates `genre-classifier` with an `s3://` `artifact_location` (not the
`mlflow-artifacts:/` proxy scheme), so `log_model` writes the blob **straight to MinIO**, bypassing the server.
Metadata + the registry entry still go through the server (small, fine). Result: the 113-MB+ model uploads in
~110s instead of dying.

> Moving compute to rogueone did **not** fix the upload by itself — the artifact still flowed *through* the
> serve-artifacts proxy regardless of where the client ran. Pointing artifacts direct at MinIO is the actual fix;
> rogueone just enables it (the client already talks to MinIO).

### One-time: purge a proxy-location experiment

If `genre-classifier` already exists with a `mlflow-artifacts:/` location (e.g. from an earlier in-cluster
attempt), the trainer refuses it. Purge on the server so it's recreated `s3://`:
```
kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'B="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@weyland-postgres.weyland.svc.cluster.local:5432/mlflow"; MLFLOW_TRACKING_URI="$B" mlflow experiments delete --experiment-id <ID>; MLFLOW_TRACKING_URI=http://localhost:5000 mlflow gc --backend-store-uri "$B" --artifacts-destination s3://mlflow/'
```
(`experiments delete` needs the DB URI; `gc` needs the **http** tracking URI to resolve the old proxy artifacts —
the DB URI alone defaults tracking to `file:///mlruns` and errors.)

---

## The gotcha gauntlet (the full trail)

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `log_model` 404 on `/api/2.0/mlflow/logged-models` | 3.x client vs 2.x server | pin `mlflow==2.18.0` |
| 2 | RF fit OOM-killed the dagster pod (exit 137) | unbounded depth × 113 classes | `n_estimators=100, max_depth=20` |
| 3 | upload hung → gunicorn `WORKER TIMEOUT` → 500 | serve-artifacts proxy relays a multi-GB blob through the 1Gi pod | artifacts **direct to MinIO** (`s3://` experiment) |
| 4 | registry `pull` fails mid-layer, 403 to `minio.svc:9000` | registry redirects to presigned MinIO URLs | `REGISTRY_STORAGE_REDIRECT_DISABLE=true` |
| 5 | IntelliJ "Unsupported registry" | Traefik basic-auth 401 lacks the docker api-version header | drop registry auth (LAN-only) |
| 6 | container can't resolve `mother` | Docker gives the container its own `/etc/hosts` | `--add-host mother:192.168.1.243` |
| 7 | `--network host` container can't reach `localhost:8000` forwards | Docker Desktop `--network host` = the *VM's* loopback | in-container port-forwards (own localhost), bridge networking |
| 8 | `connection refused` to `mother:6443` on the bridge | `--add-host` pointed at rogueone's `.230`, not mother's `.243` | correct IP |
| 9 | `pip` crash resolving `aiohttp` | the k8s Python client's dep tree + old pip | drop the client (use `kubectl`), upgrade pip |

---

## Execute

See **[services/genre-trainer/README.md](../../nodes/mother/lab/weyland-platform/services/genre-trainer/README.md)**
for build + the one run command. Summary:
```
docker build -t registry.weyland.lab/genre-trainer:v3 <path-to-genre-trainer>
docker push registry.weyland.lab/genre-trainer:v3
docker run --rm -v $HOME/.kube/config:/root/.kube/config:ro --add-host mother:192.168.1.243 registry.weyland.lab/genre-trainer:v3 --source silver
```
Then `mlflow.weyland.lab` → experiment `genre-classifier`, model `genre_classifier`.
