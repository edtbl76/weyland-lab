# Finance volatility trainer — the B113 Phase-5 ML lane

The finance analogue of the genre-classifier (see [remote-training.md](remote-training.md)): an **external**
trainer that reads the Feast-retrieved training set from lakeFS and fits + registers a **volatility regressor**
and a **vol-regime classifier** in weyland MLflow. Feast's offline store is STRICT-mTLS Postgres (unreachable
externally), so the point-in-time join runs in the meshed Dagster asset `price_feast_training_set` and lands a
parquet in lakeFS; this trainer reads that. Source: `services/finance-trainer/train_volatility.py`.

## 1. Prerequisites (run once when the price data or features change)

In the `dagster-user-code` pod (meshed, has Trino + feast Postgres + feast_repo):

```
UCPOD=$(kubectl -n weyland get pods -o name | grep dagster-user-code | head -1 | cut -d/ -f2)
kubectl -n weyland exec "$UCPOD" -c dagster-user-code -- python scripts/feast_setup.py
```

That rebuilds the `feast` offline tables from the dbt marts (including `price_features` ← `mart_price_features`),
`feast apply`s the definitions, and materializes online. It needs `mart_price_features` built first (materialize
the dbt asset or `dbt build`). Then materialize the training set (Dagster asset `price_feast_training_set`) — the
meshed point-in-time join that lands `finance/parquet/price_feast_training/` in lakeFS.

## 2. Run the trainer (rogueone)

The trainer runs on rogueone against the platform's LAN NodePorts — `mlflow-lan` `192.168.1.243:30500` (admits
rogueone only), `minio-s3-lan` `:30990`, `lakefs-lan` `:30800`; the lab never port-forwards. Export the creds from
the k8s Secrets (NEVER inline — same Secrets `services/genre-trainer/entrypoint.sh` reads), then run. A Python venv
with `mlflow scikit-learn pandas numpy minio pyarrow boto3` (+ `ray` for `--tune`) suffices.

```
export LAKEFS_ACCESS_KEY_ID=$(kubectl -n weyland get secret lakefs-creds -o jsonpath='{.data.LAKEFS_ACCESS_KEY_ID}' | base64 -d)
export LAKEFS_SECRET_ACCESS_KEY=$(kubectl -n weyland get secret lakefs-creds -o jsonpath='{.data.LAKEFS_SECRET_ACCESS_KEY}' | base64 -d)
export AWS_ACCESS_KEY_ID=$(kubectl -n weyland get secret aidlc-kb-minio-secret -o jsonpath='{.data.access_key}' | base64 -d)
export AWS_SECRET_ACCESS_KEY=$(kubectl -n weyland get secret aidlc-kb-minio-secret -o jsonpath='{.data.secret_key}' | base64 -d)
export MLFLOW_TRACKING_URI=http://192.168.1.243:30500 MLFLOW_S3_ENDPOINT_URL=http://192.168.1.243:30990
export LAKEFS_ENDPOINT=http://192.168.1.243:30800 LAKEFS_BRANCH=main AWS_DEFAULT_REGION=us-east-1

cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/finance-trainer
python train_volatility.py --task both        # add --tune for a Ray-Tune sweep (needs a Ray cluster + `ray`)
```

`--task {regress,classify,both}` (default `both`). Artifacts go DIRECT to MinIO (`s3://mlflow/…`), bypassing the
serve-artifacts proxy.

## 2b. Or run the container (durable/reproducible — `registry.weyland.lab/finance-trainer`)

`entrypoint.sh` reads the Secrets itself from a mounted kubeconfig and points the trainer at the same three
NodePorts (waiting until each answers), so the container needs no creds on the CLI. Build (on a box with docker — rogueone Docker Desktop is
amd64/x86_64, matching the cluster) + push + run:

```
cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services
docker build -t registry.weyland.lab/finance-trainer:v2 finance-trainer
bash /home/edwardmangini/IdeaProjects/weyland/scripts/push-image.sh registry.weyland.lab/finance-trainer:v2
docker run --rm -v "$HOME/.kube/config":/app/.kube/config:ro --add-host mother:192.168.1.243 registry.weyland.lab/finance-trainer:v2 --task both
```

Note the kubeconfig mounts to **`/app/.kube/config`** (the image runs as `appuser` with `HOME=/app`), NOT
`/root/.kube/config`. **Pinned since v2 (2026-10-17, B220):** `requirements.in` is the human-edited source (the
top-level deps, plus `mlflow==3.16.1` = the server and `ray[default]==2.56.0` = the ray-head cluster, which must
match); `requirements.txt` is the FULL set frozen from a clean resolve of it (119 pins, `pip check` clean) —
recompile it, never hand-edit (genre-trainer's hand-kept freeze once drifted into an unresolvable set). Unpinned, a
rebuild had resolved ray 2.59.0 against the 2.56.0 cluster. **skops >= 0.16** refuses sklearn's tree storage unless
trusted, so `log_model` passes `skops_trusted_types=["sklearn.tree._tree.Tree"]` (the model was trained in-process).
Proven 2026-10-17: `--task both` registered `price_volatility_regressor` / `_classifier` v3.

## 3. Result

Experiment **`price-volatility`** in MLflow (`https://mlflow.weyland.lab`), two registered models:
`price_volatility_regressor` (metrics RMSE, R²) and `price_volatility_classifier` (accuracy, F1). Volatility
clusters, so both carry real signal (R²>0, acc≫0.5) — unlike a returns/direction model, which would be ~coin-flip.
