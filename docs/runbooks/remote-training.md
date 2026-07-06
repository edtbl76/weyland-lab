# Runbook — Remote model training on rogueone (registry → Ray cluster → MLflow)

The platform's **remote training capability**: heavy model training runs on **rogueone** (ThinkPad P16 — 128 GB
RAM, 32 cores, RTX 5000 Ada), while weyland stays the **platform** (MLflow tracking + registry, MinIO artifacts,
lakeFS silver). weyland is the control plane, rogueone is the compute.

There are **two forms**, both live:

1. **Persistent Ray cluster (the primary path).** An always-on **Ray head** on mother (`ray.weyland.lab`) that
   rogueone joins as a **permanent native edge worker**; you **submit jobs** to it (`ray job submit`, the Ray
   dashboard, or a Port action). This is the standing home for training + hyperparameter sweeps.
2. **Self-contained trainer container (the simple path).** A single image in the registry that rogueone
   `docker run`s to completion and discards — no cluster needed. Good for a one-off fit.

First consumer of both: the **genre classifier** (`services/genre-trainer/`, `genre_classifier` registered
model). The pattern is generic — any CPU/GPU job that needs more muscle than the k3s box follows the same path.
This is **B1.8's Ray / data-science tier** (plain Ray, not KubeRay — see below); JupyterHub is still deferred.

> **Why not in-cluster?** The dagster pod is 1Gi and the k3s box is ~50 GB shared; training belongs on the box
> with the RAM + GPU. (The genre RandomForest is CPU-bound and won't touch the Ada — the GPU payoff comes when the
> trainer is a GPU framework over the same path.)

---

## Architecture — the persistent Ray cluster

```
  rogueone (.230) — native systemd worker            weyland k3s (mother, .243)
  ┌──────────────────────────────────┐               ┌──────────────────────────────────────────────┐
  │  ray-worker.service               │  join GCS     │  Ray head (k8s/ray/, plain Ray, hostNetwork)  │
  │   ray start --address=.243:6379 ──┼──── :6379 ───▶│   ray.weyland.lab (dashboard, Keycloak SSO)   │
  │   (venv = head's pip freeze)      │               │   Jobs API :8265 · --num-cpus=0 (coordinator) │
  │                                   │◀── schedule ──┤   train_genre.py baked at /home/ray/          │
  │  trials run HERE (32 cores)       │   trials      │                                                │
  │   log params/metrics ────────────┼── :30500 ────▶│  MLflow NodePort (mlflow-lan) ─▶ Postgres      │
  │   winner retrain+register ───────┼── :30500 ────▶│  MLflow ─▶ registry (genre_classifier)        │
  │   artifact (model.pkl) ──────────┼── s3.weyland.lab ─▶  MinIO  s3://mlflow/…  (DIRECT, TLS)      │
  └──────────────────────────────────┘  AWS_CA_BUNDLE └──────────────────────────────────────────────┘
```

You submit a job to the head; the head is a **coordinator only** (`--num-cpus=0`), so trials schedule onto the
rogueone worker. Metadata flows to MLflow via the **LAN NodePort `:30500`**; the model artifact goes **direct to
MinIO** (`s3.weyland.lab`, TLS verified). The **winner retrains + registers on the worker** (a `@ray.remote`
task) — keeping the big final fit off the 4Gi head pod.

### The standalone-container path (alternative)

The `genre-trainer` image also runs on its own: `docker run` it with a mounted kubeconfig and it self-fetches
creds from k8s Secrets + opens in-container `kubectl port-forward`s, reads lakeFS silver, trains, and logs to
MLflow (artifact direct to MinIO). No cluster, no submit — see **Execute** below. The container-specific gotchas
(Docker Desktop RAM cap, loopback, `--add-host`) apply only to this path.

---

## The MinIO-backed registry

`registry.weyland.lab` — a `distribution/registry` (`registry:2.8.3`) whose blobs live in a MinIO bucket
(`registry`), so the pod is **stateless** (no PVC). Manifest: `k8s/registry/registry.yaml`; Argo app in
`k8s/argocd/applications/subdir-apps.yaml`. Reusable platform-wide (this is the in-cluster registry B57 wanted).
The k3s nodes pull from it via `/etc/rancher/k3s/registries.yaml` (`insecure_skip_verify` — mkcert cert isn't in
containerd's trust).

Bring-up (once):
```
# bucket (throwaway mc pod, creds from the minio secret):
U=$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d); P=$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d); kubectl -n minio run mc-mkbucket-registry --rm -i --restart=Never --image=minio/mc --env="MC_HOST_m=http://$U:$P@minio.minio.svc.cluster.local:9000" -- mb -p m/registry
# then push k8s/registry/ + the subdir-apps.yaml entry → Argo deploys it.
```

**No auth** — LAN-only registry on a trusted LAN. DNS: add `registry.weyland.lab` to the LAN DNS / rogueone
`/etc/hosts` if there's no wildcard.

### Registry gotchas

- **`REGISTRY_STORAGE_REDIRECT_DISABLE: "true"`** — the key is `storage.redirect.disable` (a sibling of `s3`),
  so the env var is `REGISTRY_STORAGE_REDIRECT_DISABLE`, **not** `..._S3_REDIRECT_DISABLE`. Without it the
  registry redirects blob GETs to *presigned MinIO URLs* at `minio.minio.svc:9000` that external clients
  (rogueone) can't reach → `pull` fails mid-layer. Disabling redirect proxies blob bytes through the ingress.
- **No web UI** — a Docker registry is an API. `https://registry.weyland.lab/` is a blank 200; browse via
  `/v2/_catalog`, the docker CLI, or IntelliJ. (A `joxit/docker-registry-ui` front-end is a backlog follow-up.)
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
| **metadata** (params, metrics, registry entry) | through the MLflow server → Postgres | `MLFLOW_TRACKING_URI` (the NodePort `http://192.168.1.243:30500` for the external worker) |
| **artifact** (`model.pkl`) | client → **MinIO, direct** | experiment `artifact_location = s3://mlflow/<name>` + client `MLFLOW_S3_ENDPOINT_URL=https://s3.weyland.lab`/`AWS_*` |

The trainer's `ensure_experiment` creates `genre-classifier` with an `s3://` `artifact_location` (not the
`mlflow-artifacts:/` proxy scheme), so `log_model` writes the blob **straight to MinIO**, bypassing the server.
Metadata + the registry entry still go through the server (small, fine).

> Moving compute to rogueone did **not** fix the upload by itself — the artifact still flowed *through* the
> serve-artifacts proxy regardless of where the client ran. Pointing artifacts direct at MinIO is the actual fix.

**TLS to MinIO is verified, not skipped.** The external worker sets **`AWS_CA_BUNDLE`** to the mkcert root
(`/home/edwardmangini/.local/share/mkcert/rootCA.pem`, baked into `ray-worker.service`), so boto3 verifies
`s3.weyland.lab` — this **replaced** the earlier `MLFLOW_S3_IGNORE_TLS` (no more `InsecureRequestWarning` spam).

### One-time: purge a proxy-location experiment

If `genre-classifier` already exists with a `mlflow-artifacts:/` location (e.g. from an earlier in-cluster
attempt), the trainer refuses it. Purge on the server so it's recreated `s3://`:
```
kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'B="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@weyland-postgres.weyland.svc.cluster.local:5432/mlflow"; MLFLOW_TRACKING_URI="$B" mlflow experiments delete --experiment-id <ID>; MLFLOW_TRACKING_URI=http://localhost:5000 mlflow gc --backend-store-uri "$B" --artifacts-destination s3://mlflow/'
```
(`experiments delete` needs the DB URI; `gc` needs the **http** tracking URI to resolve the old proxy artifacts —
the DB URI alone defaults tracking to `file:///mlruns` and errors.)

---

## The persistent Ray cluster (head + edge worker)

**Head — always-on, on mother.** `k8s/ray/ray-head.yaml`: a plain-Ray Deployment (image
`registry.weyland.lab/ray-head`, built from `services/ray-head/` = `rayproject/ray:2.37.0-py311` + the trainer
deps + `train_genre.py` baked at `/home/ray/`). `hostNetwork: true` so an **external** worker can reach the GCS on
mother's real IP; `--num-cpus=0` makes the head a **coordinator only** (the driver runs here, trials schedule onto
workers). Dashboard/Jobs API on `:8265`; GCS `:6379`. The dashboard is at `ray.weyland.lab` (Keycloak forward-auth);
the in-cluster Jobs API (for a Port action) is `ray-head.weyland.svc:8265`. Submitted jobs **inherit the head's
env** (MLflow NodePort, MinIO S3 endpoint, lakeFS svc-DNS, creds from Secrets), so a job needs no args to find the
platform.

**Why plain Ray, not KubeRay.** KubeRay only manages **in-cluster pod** workers — it can't enroll an external,
not-always-on laptop. A plain `ray start` cluster can. So the head is a normal Deployment and rogueone joins with
native `ray start --address`. (This is the reverse of the earlier "local Ray inside the container" stage — the
cluster is now standing and shared.)

**Edge worker — rogueone, native, systemd.** `services/ray-head/ray-worker.service`:
```
ExecStart=/home/edwardmangini/ray-worker/bin/ray start --address=192.168.1.243:6379 --node-ip-address=192.168.1.230 --block
Environment=AWS_CA_BUNDLE=/home/edwardmangini/.local/share/mkcert/rootCA.pem
Restart=always
```
`--block` runs the raylet in the foreground; on GCS disconnect it exits and `Restart=always` restarts it. This is
what "**permanent but not always-up**" means: rogueone is a laptop — on sleep/poweroff the node just drops from the
cluster and submitted jobs queue; on wake/boot the raylet exits on GCS-disconnect and systemd **auto-rejoins**.

Install (on rogueone):
```
sudo cp services/ray-head/ray-worker.service /etc/systemd/system/ray-worker.service
sudo systemctl daemon-reload && sudo systemctl enable --now ray-worker
systemctl status ray-worker --no-pager     # verify it joined
```

### Environment parity — the whole battle

A native Ray worker **must exactly match the head** or the cluster fails in opaque ways (Ray version handshake,
then pyarrow/numpy pickle/serialization ABI mismatches, then the boto3 upload). The trail we hit:

| Layer | Requirement | Failure if mismatched |
|---|---|---|
| Python | **3.11.9** (patch-exact, via `pyenv`) | Ray rejects the worker on version mismatch |
| Ray | `ray[tune]==2.37.0` (not `ray[default]`) | `fsspec` / `ray.tune` ImportError |
| Serialization | `pyarrow==14.0.2`, `numpy==1.26.4`, `pandas==1.5.3`, `scikit-learn`, `mlflow==2.18.0` | `LocalFileSystem._reconstruct` / numpy ABI errors mid-sweep |
| S3 client | `boto3==1.26.76`, `botocore==1.29.165`, `s3transfer==0.6.2` | `UnboundLocalError` in botocore `serialize.py` on artifact upload |

**The durable fix is to build the worker venv from the head's `pip freeze`** — one source of truth, no
whack-a-mole:
```
# on mother:  capture the head's exact env
kubectl -n weyland exec deploy/ray-head -- pip freeze > head-freeze.txt   # copy head-freeze.txt to rogueone
# on rogueone: recreate the venv against it
pyenv install -s 3.11.9
rm -rf ~/ray-worker && ~/.pyenv/versions/3.11.9/bin/python -m venv ~/ray-worker
~/ray-worker/bin/pip install -U pip && ~/ray-worker/bin/pip install -r head-freeze.txt py-spy
sudo systemctl restart ray-worker
```
(A failed start can leave an **orphan raylet** advertising the wrong CPU/GPU count — clear it with
`~/ray-worker/bin/ray stop --force; pkill -9 -f raylet` before restarting.)

---

## Hyperparameter sweeps — Ray Tune (`--tune`)

`--tune` runs a **Ray Tune** sweep **across the cluster** (trials on the rogueone worker) instead of a single fit.
Each trial trains an RF with a sampled config, logs its **own MLflow run** (params + metrics, no artifact), and
reports `f1_macro` to Tune. The **best config is then retrained on the full split and registered** as a new
`genre_classifier` version — but that retrain runs as a **`@ray.remote` task on the worker**, not on the head, so
the big final fit + artifact upload never OOMs the 4Gi head pod (an earlier version retrained on the head → exit
137). One sweep = N comparable experiment runs + **1** registered winner (not N GB-scale artifacts).

Search space (bounded so 113-class forests stay memory-sane under parallelism): `n_estimators ∈ {100,200}`,
`max_depth ∈ {12,16,20}`, `max_features ∈ {sqrt,log2}`, `min_samples_leaf ∈ {1,2,4}`; 4 CPUs/trial → ~8 concurrent
on 32. **Measured:** a 24-trial sweep beats the single fit — best **f1 ~0.308 / acc ~0.327** — and registered the
winner as `genre_classifier` (~v6).

### Ray Dashboard

The dashboard is now **persistent** at `ray.weyland.lab` (Keycloak forward-auth) — live trials, per-trial logs,
CPU/GPU usage, submitted-job history. (It survives individual jobs, unlike the old ephemeral per-`docker run`
dashboard.) The unauthenticated **Jobs API is an RCE surface**, so it is **not** on the LAN directly — reachable
only via the SSO ingress (browser) or the in-cluster svc (the Port action). `py-spy` on the worker gives flame
graphs / stack traces for a running trial.

---

## Hardening

- **MLflow LAN NodePort pinned to rogueone.** `mlflow-lan` (`:30500`) is unauthenticated MLflow on the LAN.
  `externalTrafficPolicy: Local` preserves the client source IP so a host firewall rule can pin it to the worker:
  ```
  sudo iptables -I INPUT 1 -p tcp --dport 30500 ! -s 192.168.1.230 -j DROP
  ```
  (On **mother**. **Not yet reboot-persistent** — a follow-up is to persist the nft/iptables rule.)
- **MinIO TLS verified** via `AWS_CA_BUNDLE` (mkcert root in the systemd unit), not skipped.
- **Ray dashboard** SSO-gated; the Jobs API stays off the LAN.
- **Residual (backlog B-RT):** the `hostNetwork` head still exposes Ray ports on the LAN. Proper fix = a
  segmented VLAN/firewall allow-list + Ray TLS / join-token (Ray is not a security boundary → constrain at the
  network / DMZ).

---

## The gotcha gauntlet (the full trail)

| # | Symptom | Root cause | Fix | Path |
|---|---|---|---|---|
| 1 | `log_model` 404 on `/api/2.0/mlflow/logged-models` | 3.x client vs 2.x server | pin `mlflow==2.18.0` | both |
| 2 | RF fit OOM-killed the pod (exit 137) | unbounded depth × 113 classes | `n_estimators≤200, max_depth≤20` | both |
| 3 | upload hung → gunicorn `WORKER TIMEOUT` → 500 | serve-artifacts proxy relays a multi-GB blob through the 1Gi pod | artifacts **direct to MinIO** (`s3://` experiment) | both |
| 4 | registry `pull` fails mid-layer, 403 to `minio.svc:9000` | registry redirects to presigned MinIO URLs | `REGISTRY_STORAGE_REDIRECT_DISABLE=true` | both |
| 5 | IntelliJ "Unsupported registry" | Traefik basic-auth 401 lacks the docker api-version header | drop registry auth (LAN-only) | both |
| 6 | container can't resolve `mother` | Docker gives the container its own `/etc/hosts` | `--add-host mother:192.168.1.243` | container |
| 7 | `--network host` container can't reach `localhost:8000` forwards | Docker Desktop `--network host` = the *VM's* loopback | in-container port-forwards (own localhost), bridge networking | container |
| 8 | `connection refused` to `mother:6443` on the bridge | `--add-host` pointed at rogueone's `.230`, not mother's `.243` | correct IP | container |
| 9 | `pip` crash resolving `aiohttp` | the k8s Python client's dep tree + old pip | drop the client (use `kubectl`), upgrade pip | container |
| 10 | Ray Tune trials OOM at **15.6 GB** on a 128 GB box | **Docker Desktop caps the container's memory** (its VM allocation) | raise Docker Desktop → Resources → Memory | container |
| 11 | Ray Dashboard = **unauth RCE** on the LAN | publishing `:8265` on the host `0.0.0.0` | loopback-only (`-p 127.0.0.1:8265`) for the container path; the persistent head keeps it SSO-gated | both |
| 12 | worker rejected / `fsspec` / pyarrow ABI errors mid-sweep | worker env drifted from the head (python / ray / serialization libs) | build the worker venv from the head's `pip freeze` (parity table above) | cluster |
| 13 | `UnboundLocalError` in botocore `serialize.py` on upload | `boto3`/`botocore`/`s3transfer` drifted on the worker | pin the trio to the head's (`1.26.76`/`1.29.165`/`0.6.2`) | cluster |
| 14 | winner retrain exit 137 after the sweep | retraining the winner on the 4Gi head pod | run it as a `@ray.remote` task on the worker | cluster |
| 15 | orphan raylet advertises wrong CPU/GPU count | a failed `ray start` left a raylet behind | `ray stop --force; pkill -9 -f raylet` before restarting | cluster |

---

## Execute

**Persistent-cluster path (primary):**
```
# ensure the worker is up (rogueone):  systemctl status ray-worker
# submit from mother (or the ray.weyland.lab dashboard / a Port action):
kubectl -n weyland exec deploy/ray-head -- ray job submit --address http://localhost:8265 -- python /home/ray/train_genre.py --source silver --tune --trials 24
```

**Standalone-container path (one-off fit):** see
**[services/genre-trainer/README.md](../../nodes/mother/lab/weyland-platform/services/genre-trainer/README.md)**.
```
docker build -t registry.weyland.lab/genre-trainer:v3 <path-to-genre-trainer>
docker push registry.weyland.lab/genre-trainer:v3
docker run --rm -v $HOME/.kube/config:/root/.kube/config:ro --add-host mother:192.168.1.243 registry.weyland.lab/genre-trainer:v3 --source silver
```
Then `mlflow.weyland.lab` → experiment `genre-classifier`, model `genre_classifier`.
