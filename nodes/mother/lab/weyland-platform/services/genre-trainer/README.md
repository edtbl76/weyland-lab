# genre-trainer — remote training on rogueone

The weyland platform's **remote training job**. Training compute belongs on **rogueone** (72Gi RAM, real cores),
not the weyland k3s cluster — weyland is the *platform* (MLflow tracking + registry, MinIO artifacts, lakeFS
silver). This image is built + pushed to the MinIO-backed registry, then pulled + run **ephemerally** on
rogueone: pull → train → log to MLflow → exit (`docker run --rm`).

## What it does

Trains a **genre classifier** (RandomForest, Spotify audio features → `track_genre`) and logs it to the weyland
MLflow. The design point is the **two-plane MLflow split**:

| Plane | Path | Why |
|---|---|---|
| **metadata** (params, metrics, registry entry) | client → MLflow server → Postgres | small, always fine |
| **artifact** (the model blob) | client → **MinIO, direct** (`s3://mlflow/…`) | **bypasses** the server's `--serve-artifacts` proxy, so a large `model.pkl` never squeezes through the 1Gi MLflow pod (which timed out relaying it) |

Direct artifact upload works because the `genre-classifier` experiment is created with an `s3://` `artifact_location`
instead of the `mlflow-artifacts:/` proxy scheme. That's the whole reason moving compute to rogueone *plus*
pointing artifacts at MinIO fixes the upload — see `docs/runbooks/mlflow-training.md`.

## Build + push (on rogueone)

```
docker build -t registry.weyland.lab/genre-trainer:v1 nodes/mother/lab/weyland-platform/services/genre-trainer
docker push registry.weyland.lab/genre-trainer:v1
```

(The push is also the registry's end-to-end proof — blobs land in MinIO's `registry` bucket.)

## One-time: purge the old proxy experiment

The first in-cluster attempts created a `genre-classifier` experiment (id 3) with a **proxy** `artifact_location`.
The trainer refuses to reuse it (it would upload through the proxy and time out). Purge it once so it's recreated
with a direct `s3://` location — **[mother]**:

```
kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'B="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@weyland-postgres.weyland.svc.cluster.local:5432/mlflow"; MLFLOW_TRACKING_URI="$B" mlflow experiments delete --experiment-id 3; mlflow gc --backend-store-uri "$B" --artifacts-destination s3://mlflow/'
```

## Run (on rogueone)

Forward three cluster services to rogueone's localhost via the **IntelliJ Kubernetes plugin** (Services → svc →
Forward Ports):

| Service | Namespace | Local port |
|---|---|---|
| `mlflow` | weyland | 5000 |
| `minio` | minio | 9000 |
| `lakefs` | data-mesh | 8000 |

Then run the ephemeral trainer (`--network host` so the container reaches those forwards; `--rm` = teardown on
exit). Fill in the lakeFS + MinIO creds:

```
docker run --rm --network host \
  -e MLFLOW_TRACKING_URI=http://localhost:5000 \
  -e MLFLOW_S3_ENDPOINT_URL=http://localhost:9000 \
  -e AWS_ACCESS_KEY_ID=<minio-access-key> -e AWS_SECRET_ACCESS_KEY=<minio-secret-key> -e AWS_DEFAULT_REGION=us-east-1 \
  -e LAKEFS_ENDPOINT=http://localhost:8000 -e LAKEFS_BRANCH=main \
  -e LAKEFS_ACCESS_KEY_ID=<lakefs-access-key> -e LAKEFS_SECRET_ACCESS_KEY=<lakefs-secret-key> \
  registry.weyland.lab/genre-trainer:v1 --source silver
```

Watch for `acc=… f1_macro=…` then `model logged + registered as 'genre_classifier'`. View it at
`mlflow.weyland.lab` → experiment `genre-classifier`, registered model `genre_classifier`.

## Sources

- `--source silver` — read `spotify_tracks` silver straight from lakeFS. **Implemented.**
- `--source feast` — features from Feast (`get_historical_features`, point-in-time). *Next iteration* (needs the
  feast repo baked in + Postgres/Valkey reach). Same MLflow logging; only the feature retrieval changes.

Config is entirely env-driven (also settable: `SOURCE`, `N_ESTIMATORS`, `MAX_DEPTH`, `EXPERIMENT`,
`REGISTERED_MODEL`) so the same image runs unchanged wherever it can reach the three endpoints.
