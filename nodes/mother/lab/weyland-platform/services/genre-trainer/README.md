# genre-trainer — remote model training on rogueone

The weyland platform's **remote training job**. Training compute runs on **rogueone** (the ThinkPad P16 laptop —
128 GB RAM, 32 cores, RTX 5000 Ada), **not** the weyland k3s cluster. weyland is the *platform* (MLflow tracking
+ registry, MinIO artifacts, lakeFS silver); rogueone is the *muscle*. The image is built + pushed to the
MinIO-backed registry, then **pulled + run ephemerally** on rogueone: pull → train → log to MLflow → exit
(`docker run --rm`). Given just a mounted kubeconfig it is fully self-contained — it fetches its own creds and
opens its own port-forwards.

> Full architecture, the registry, and the hard-won gotcha list: **[docs/runbooks/remote-training.md](../../../../../../docs/runbooks/remote-training.md)**.
> The three documentable use cases + real numbers: **[docs/runbooks/mlflow-training.md](../../../../../../docs/runbooks/mlflow-training.md)**.

---

## What it does

Trains a **genre classifier** (RandomForest, Spotify audio features → `track_genre`) and logs it to weyland
MLflow. The design point is the **two-plane MLflow split** that lets a large model actually upload:

| Plane | Path | Why |
|---|---|---|
| **metadata** (params, metrics, registry entry) | client → MLflow server → Postgres | small, always fine |
| **artifact** (`model.pkl`) | client → **MinIO, direct** (`s3://mlflow/…`) | **bypasses** the server's `--serve-artifacts` proxy — a multi-GB model.pkl through the 1Gi MLflow pod times out; direct to MinIO it doesn't |

Direct upload works because the trainer creates the `genre-classifier` experiment with an **`s3://`**
`artifact_location` (not the `mlflow-artifacts:/` proxy scheme).

## How it's self-contained

The container is handed **only a mounted kubeconfig** (`~/.kube/config`). From that, `entrypoint.sh` uses
`kubectl` to:
1. **read the creds** from the k8s Secrets (`lakefs-creds`, `aidlc-kb-minio-secret`) → exports them — *no
   secret ever appears on the command line*;
2. **open port-forwards** to `mlflow` / `minio` / `lakefs` on the **container's own** localhost — no host
   port-forwards, no `--network host`, no host-loopback problems (rogueone runs Docker Desktop, whose
   `--network host` is the VM's loopback, not the host's).

Then it execs the pure-Python trainer (`train_genre.py`), which reads its config from env.

---

## Prerequisites (one-time)

- **The registry is up** — `registry.weyland.lab` (see the runbook). `docker` on rogueone can pull from it.
- **rogueone has a working kubeconfig** at `~/.kube/config` whose user can read Secrets **and** `create
  pods/portforward` in the cluster (the same one IntelliJ's k8s plugin uses).
- The `spotify_tracks` silver exists in lakeFS (`music` repo, `main/parquet/spotify_tracks/`).

## Build + push (on rogueone)

```
docker build -t registry.weyland.lab/genre-trainer:v3 nodes/mother/lab/weyland-platform/services/genre-trainer
docker push registry.weyland.lab/genre-trainer:v3
```

## Run (on rogueone)

```
DOCKER_HOST=unix:///var/run/docker.sock docker run --rm -v $HOME/.kube/config:/root/.kube/config:ro --add-host mother:192.168.1.243 registry.weyland.lab/genre-trainer:v3 --source silver
```

That's the **entire** run — no creds, no endpoint env, no host port-forwards. Three parts carry it:
- `DOCKER_HOST=unix:///var/run/docker.sock` — pin to rogueone's **native** docker engine (Docker Desktop retired, B127);
  native has no VM RAM cap, so the container sees all 128 GB. Same as the `scripts/gpu-docker` wrapper + the `*-bench.sh`.
- `-v $HOME/.kube/config:/root/.kube/config:ro` — the kubeconfig the container self-serves everything from.
- `--add-host mother:192.168.1.243` — so the container resolves the kubeconfig's `mother:6443` API server
  (mother is `.243`; **not** rogueone's `.230`) on the native bridge, which has no other resolver for it.

Expected output:
```
[entrypoint] reading creds from k8s Secrets via the mounted kubeconfig...
[entrypoint] port-forward weyland/mlflow -> localhost:5000        (+ minio, lakefs)
[entrypoint] localhost:5000 ready                                 (+ 9000, 8000)
[trainer] spotify silver: 89,741 rows / 113 genres after cleaning
[trainer] [silver] fit complete in ~2s — scoring…
[trainer] [silver] acc=0.321 f1_macro=0.305
[trainer] logging to MLflow ... artifact uploads DIRECT to MinIO…
[trainer] model logged + registered as 'genre_classifier' in ~110s
[trainer] done.
```

View it at `mlflow.weyland.lab` → experiment **`genre-classifier`**, registered model **`genre_classifier`**.

## Hyperparameter sweep (Ray Tune)

Append `--tune` for a **Ray Tune** sweep on a local Ray cluster (rogueone's cores): `--trials` trials (default 24),
each its own MLflow run, the best config retrained + registered. Publish the Ray Dashboard **loopback-only** (it's
unauthenticated → its Jobs API is RCE):
```
DOCKER_HOST=unix:///var/run/docker.sock docker run --rm --shm-size=2g -p 127.0.0.1:8265:8265 -v $HOME/.kube/config:/root/.kube/config:ro --add-host mother:192.168.1.243 registry.weyland.lab/genre-trainer:v6 --source silver --tune --trials 100
```
Watch at `http://localhost:8265` (rogueone, while it runs) + MLflow `genre-classifier` (persistent). Measured: the
sweep beat the single fit — **f1 0.312 / acc 0.329** vs 0.305 / 0.321.

> **Memory:** on the **native** engine (B127 — `DOCKER_HOST=unix:///var/run/docker.sock`, as above) a container sees
> rogueone's full 128 GB directly — no VM cap, no Settings knob. (Historically, under the retired Docker Desktop a
> container only saw the Desktop VM's RAM and a parallel sweep OOM'd at ~15 GB — the single setting that silently
> defeated "rogueone has the RAM." Native removes that failure mode entirely.)

## Sources (`--source`)

- **`silver`** — read `spotify_tracks` silver straight from lakeFS. **Implemented.**
- **`feast`** — features from Feast (`get_historical_features`, point-in-time). *Next iteration* — same MLflow
  logging, only the feature retrieval changes (needs the feast repo + Postgres/Valkey reach).

Also settable via env (`-e`): `SOURCE`, `N_ESTIMATORS`, `MAX_DEPTH`, `EXPERIMENT`, `REGISTERED_MODEL`, and any
endpoint/cred override (env wins over the kubeconfig fetch).

---

## Gotchas hit building this (so you don't re-hit them)

- **`--add-host` must point at mother (`.243`), not rogueone (`.230`).** Wrong IP → `kubectl` gets
  `connection refused` to the API on the bridge. (Docker Desktop `--network host` masks it — it uses the host's
  real resolver and ignores `--add-host`.)
- **No `--network host`.** On Docker Desktop it shares the *VM's* loopback, so the container can't reach
  rogueone's `127.0.0.1` (IntelliJ forwards) anyway — the in-container forwards sidestep the whole problem.
- **Docker Desktop caps container memory** (`--tune`) — the container sees the VM's RAM, not rogueone's 128 GB;
  raise Docker Desktop → Resources → Memory or a parallel sweep OOMs at ~15 GB.
- **Ray Dashboard is unauthenticated (Jobs API = RCE)** — publish it loopback-only (`-p 127.0.0.1:8265:8265`),
  never `-p 8265:8265` (that's the host's `0.0.0.0` → LAN-reachable).
- **MLflow client pinned to `2.18.0`** = the deployed server version. An unpinned 3.x client calls
  `/api/2.0/mlflow/logged-models` (404 on the 2.x server).
- **`RandomForest` is bounded** (`n_estimators=100, max_depth=20`). Unbounded × 113 classes made the pickle
  multi-GB and the fit memory-hungry.
- **The experiment must have an `s3://` artifact_location.** If a `genre-classifier` already exists with the
  `mlflow-artifacts:/` (proxy) scheme, the trainer refuses it — purge it on the server so it's recreated direct:
  ```
  kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'B="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@weyland-postgres.weyland.svc.cluster.local:5432/mlflow"; MLFLOW_TRACKING_URI="$B" mlflow experiments delete --experiment-id <ID>; MLFLOW_TRACKING_URI=http://localhost:5000 mlflow gc --backend-store-uri "$B" --artifacts-destination s3://mlflow/'
  ```
