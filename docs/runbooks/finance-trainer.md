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

The trainer runs on rogueone against in-container/host port-forwards. Open the three forwards, export the creds
from the k8s Secrets (NEVER inline — same Secrets `services/genre-trainer/entrypoint.sh` reads), then run. A
Python venv with `mlflow scikit-learn pandas numpy minio pyarrow boto3` (+ `ray` for `--tune`) suffices.

```
kubectl port-forward -n weyland   svc/mlflow 5000:5000 >/dev/null 2>&1 &
kubectl port-forward -n minio     svc/minio  9000:9000 >/dev/null 2>&1 &
kubectl port-forward -n data-mesh svc/lakefs 8000:8000 >/dev/null 2>&1 &

export LAKEFS_ACCESS_KEY_ID=$(kubectl -n weyland get secret lakefs-creds -o jsonpath='{.data.LAKEFS_ACCESS_KEY_ID}' | base64 -d)
export LAKEFS_SECRET_ACCESS_KEY=$(kubectl -n weyland get secret lakefs-creds -o jsonpath='{.data.LAKEFS_SECRET_ACCESS_KEY}' | base64 -d)
export AWS_ACCESS_KEY_ID=$(kubectl -n weyland get secret aidlc-kb-minio-secret -o jsonpath='{.data.access_key}' | base64 -d)
export AWS_SECRET_ACCESS_KEY=$(kubectl -n weyland get secret aidlc-kb-minio-secret -o jsonpath='{.data.secret_key}' | base64 -d)
export MLFLOW_TRACKING_URI=http://localhost:5000 MLFLOW_S3_ENDPOINT_URL=http://localhost:9000
export LAKEFS_ENDPOINT=http://localhost:8000 LAKEFS_BRANCH=main AWS_DEFAULT_REGION=us-east-1

cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/finance-trainer
python train_volatility.py --task both        # add --tune for a Ray-Tune sweep (needs a Ray cluster + `ray`)
```

`--task {regress,classify,both}` (default `both`). The container path (durable/reproducible) is the same as
genre-trainer: `entrypoint.sh` opens the forwards + reads the Secrets itself from a mounted kubeconfig — build
`services/finance-trainer/Dockerfile`, push to `registry.weyland.lab`, `docker run --rm` it. Artifacts go DIRECT
to MinIO (`s3://mlflow/…`), bypassing the serve-artifacts proxy.

## 3. Result

Experiment **`price-volatility`** in MLflow (`https://mlflow.weyland.lab`), two registered models:
`price_volatility_regressor` (metrics RMSE, R²) and `price_volatility_classifier` (accuracy, F1). Volatility
clusters, so both carry real signal (R²>0, acc≫0.5) — unlike a returns/direction model, which would be ~coin-flip.
