# Demo — Remote Training (Ray cluster → MLflow + MinIO registry)

Heavy model training runs on **rogueone** (ThinkPad P16 — 128 GB RAM, 32 cores, RTX 5000 Ada) while
weyland stays the platform (MLflow tracking + registry, MinIO artifacts, lakeFS silver). The
primary path is the **persistent Ray cluster**: an always-on Ray head on `mother`
(`ray.weyland.lab`, `--num-cpus=0` coordinator) that rogueone joins as a permanent native edge
worker (`ray-worker.service`); you `ray job submit` to it. Trials run on the worker, log
params/metrics to MLflow via the LAN NodePort `:30500`, the winner retrains as a `@ray.remote` task
on the worker, and the `model.pkl` uploads **direct to MinIO** (`s3://mlflow/…`, TLS via
`AWS_CA_BUNDLE`). First consumer: the **genre classifier** (`genre_classifier` registered model).
Full mechanics + the gotcha gauntlet: [../runbooks/remote-training.md](../runbooks/remote-training.md).

## Sequence diagram

```mermaid
sequenceDiagram
    participant Op as Operator (mother)
    participant Head as Ray head (ray.weyland.lab, coordinator num-cpus=0)
    participant Wk as Ray worker (rogueone, 32 cores)
    participant ML as MLflow (LAN NodePort :30500)
    participant PG as Postgres (mlflow db)
    participant S3 as MinIO (s3://mlflow)
    Op->>Head: ray job submit train_genre.py --source silver --tune --trials 24
    Head->>Wk: schedule trials (head is coordinator only)
    Wk->>ML: log params/metrics per trial (http :30500, unauth LAN)
    ML->>PG: write runs
    Wk->>Wk: retrain winner (@ray.remote task on the worker)
    Wk->>S3: PUT model.pkl DIRECT (TLS via AWS_CA_BUNDLE)
    Wk->>ML: register genre_classifier version
    ML->>PG: write registered version
    ML-->>Op: run_id + registered version
```

## Prerequisites

- `mother` — Ray head (`k8s/ray/`, `ray.weyland.lab`, GCS `:6379`, Jobs API `:8265`), MLflow LAN
  NodePort `mlflow-lan` (`192.168.1.243:30500`), MinIO, lakeFS silver.
- `rogueone` — the native Ray edge worker must be up: `systemctl status ray-worker`. Its venv is
  built from the head's `pip freeze` (env parity); `AWS_CA_BUNDLE` is baked into the systemd unit.
- The MinIO-backed OCI registry `registry.weyland.lab` (the ray-head image lives here; build+push on
  rogueone, which trusts the mkcert CA).
- For `--source feast` / `--source mart`, materialize the bridge asset first (see below).
- UIs: `ray.weyland.lab` (Keycloak forward-auth), `mlflow.weyland.lab`. Login `emangini` /
  `weyland_dev_password`.

## UI walkthrough

1. Confirm the worker: open `https://ray.weyland.lab` (Keycloak SSO) → **Cluster** — the rogueone
   node (`192.168.1.230`, 32 CPUs) should be present; the head shows 0 CPUs (coordinator).
2. After submitting (below), watch **Jobs** / live trials, per-trial logs, and CPU/GPU usage in the
   Ray dashboard. Read Ray metrics natively at `grafana.weyland.lab` → **Dashboards → Ray** (the
   in-tab Metrics embed is eye-candy).
3. Open `https://mlflow.weyland.lab` → experiment **`genre-classifier`**: one MLflow run per Tune
   trial (params + `f1_macro`); **Models → `genre_classifier`** shows the new registered version
   (the sweep winner).

## CLI walkthrough

Ensure the worker is joined:

[rogueone] `systemctl status ray-worker --no-pager`

Submit the sweep to the persistent cluster from the head pod (primary path):

[mother] `kubectl -n weyland exec deploy/ray-head -- ray job submit --address http://localhost:8265 -- python /home/ray/train_genre.py --source silver --tune --trials 24`

Train from the TESTED dbt mart instead (materialize the in-cluster bridge export first):

[mother] `kubectl -n weyland exec deploy/dagster-user-code -- dagster asset materialize --select mart_spotify_audio_export -m weyland_pipeline.definitions`

[mother] `kubectl -n weyland exec deploy/ray-head -- ray job submit --address http://localhost:8265 -- python /home/ray/train_genre.py --source mart --tune --trials 24`

Standalone-container path (one-off fit, no cluster) on rogueone:

[rogueone] `docker run --rm -v $HOME/.kube/config:/root/.kube/config:ro --add-host mother:192.168.1.243 registry.weyland.lab/genre-trainer:v3 --source silver`

Confirm the artifact landed direct in MinIO:

[mother] `mc ls --recursive weyland/mlflow/`

## Expected result

- The Ray job completes; the dashboard shows N Tune trials on the rogueone worker.
- MLflow experiment `genre-classifier` gains N trial runs + **1** new registered `genre_classifier`
  version (a sweep = N comparable runs, not N GB-scale artifacts). Measured baseline: single fit
  `accuracy ≈ 0.321 / f1_macro ≈ 0.305`; a 24-trial sweep beats it (best `f1 ≈ 0.308 / acc ≈ 0.327`).
- The winner's `model.pkl` is in MinIO under `s3://mlflow/genre-classifier/…`.

## Cleanup / teardown

This run creates real data: MLflow trial runs, a registered `genre_classifier` version, and the
MinIO artifact. To remove a demo run's output:

Delete a specific registered model version (from the MLflow pod against the http tracking URI):

[mother] `kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'MLFLOW_TRACKING_URI=http://localhost:5000 mlflow models delete-version --name genre_classifier --version <N>'`

Delete the trial runs by deleting/re-creating a throwaway experiment, or delete individual runs in
the MLflow UI (run → **Delete**). Then GC the orphaned artifacts (the DB URI form from the runbook):

[mother] `kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'B="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@weyland-postgres.weyland.svc.cluster.local:5432/mlflow"; MLFLOW_TRACKING_URI=http://localhost:5000 mlflow gc --backend-store-uri "$B" --artifacts-destination s3://mlflow/'`

> The `mlflow models delete-version` invocation is `TODO: verify` against the pinned MLflow 3.14
> CLI; the UI path (Models → `genre_classifier` → version → **Delete**) is the always-available
> equivalent. Do not delete the whole `genre_classifier` model unless you intend to drop every
> version. The Ray worker + head are long-lived infrastructure — leave them running (submitted jobs
> just queue when rogueone sleeps).
