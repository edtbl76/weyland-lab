# Demo — ML lifecycle end-to-end (silver → Feast → Ray train → MLflow register → serve/consume)

> **Pending live end-to-end validation run.** Every command is real and pulled from the ML runbooks/demos it
> threads, but this straight-through lifecycle — especially the final **consume** leg — has **not** yet been
> executed end-to-end against live infra.

The full model lifecycle for the **`genre_classifier`**, threading four component demos plus the leg none of them
close — **consuming the registered model**:

1. **Silver → features** — Feast serves the Spotify audio features point-in-time ([feast.md](feast.md)); the
   in-cluster bridge asset `genre_feast_training_set` does the leakage-free `get_historical_features` join.
2. **Train + HP sweep** — a Ray Tune sweep runs on the rogueone edge worker ([remote-training.md](remote-training.md)).
3. **Register** — the winner is registered as a new `genre_classifier` version in MLflow ([mlflow.md](mlflow.md)).
4. **Serve / consume** — **the missing leg**: load `models:/genre_classifier/latest` from the registry and score
   a sample, proving the registered artifact is a usable model, not just a catalog row.

**Current reality:** heavy training runs on **rogueone** (`192.168.1.230`, RTX 5000 Ada, 32 cores); weyland
(mother) is the control plane (MLflow tracking + registry, MinIO artifacts, lakeFS silver). Ray head is a
coordinator (`--num-cpus=0`); trials schedule onto the rogueone worker.

## Sequence diagram

```mermaid
sequenceDiagram
    actor Op as Operator (mother)
    participant Bridge as genre_feast_training_set (Dagster, meshed)
    participant Feast as Feast (offline PG, point-in-time)
    participant Lake as lakeFS (training parquet)
    participant Head as Ray head (coordinator, num-cpus=0)
    participant Wk as Ray worker (rogueone, 32 cores)
    participant ML as MLflow (registry + NodePort :30500)
    participant S3 as MinIO (s3://mlflow)
    participant Cons as Consumer (load models:/genre_classifier/latest)

    Op->>Bridge: materialize genre_feast_training_set
    Bridge->>Feast: get_historical_features (as-of join)
    Bridge->>Lake: write music/parquet/genre_feast_training/
    Op->>Head: ray job submit train_genre.py --source feast --tune --trials 24
    Head->>Wk: schedule trials
    Wk->>ML: log params/metrics per trial
    Wk->>Wk: retrain winner (@ray.remote task)
    Wk->>S3: PUT model.pkl DIRECT (TLS via AWS_CA_BUNDLE)
    Wk->>ML: register genre_classifier version
    Cons->>ML: resolve models:/genre_classifier/latest → artifact URI
    Cons->>S3: fetch model.pkl
    Cons-->>Op: predict(sample) → genre label
```

## Prerequisites

Union of the component demos' prerequisites:

- **Feast** — offline/registry = Postgres `feast` DB, online = Valkey; SDK in `deploy/dagster-user-code`. The
  bridge asset `genre_feast_training_set` runs in-cluster + meshed (Feast offline is STRICT-mTLS Postgres,
  unreachable from the external trainer). See [feast.md](feast.md).
- **Ray cluster** — always-on head on mother (`ray.weyland.lab`, Jobs API `:8265`, token auth `RAY_AUTH_MODE=token`)
  + the rogueone native worker (`systemctl status ray-worker`). Worker venv is Python **3.11.14**, built from the
  head's dep set (env parity). See [remote-training.md](remote-training.md).
- **MLflow** — server `deploy/mlflow` (ns `weyland`), registry in Postgres, artifacts direct to MinIO
  (`s3://mlflow`). External clients use the LAN NodePort `http://192.168.1.243:30500` (iptables-pinned to
  rogueone). See [mlflow.md](mlflow.md).
- **MinIO** — `s3.weyland.lab`; clients verify TLS via `AWS_CA_BUNDLE` (mkcert root), not skip it.
- `kubectl` runs on **mother** (`emangini@mother`); the compute box is `edwardmangini@rogueone`.

## UI walkthrough

1. **Features** — open `https://feast-ui.weyland.lab` (Keycloak) → confirm the `track_audio_features` view /
   `track` entity exist (the training features). Materialize the bridge asset in Dagster:
   `https://dagster.weyland.lab` → Assets → `genre_feast_training_set` → **Materialize**.
2. **Train** — open `https://ray.weyland.lab` (Keycloak; paste the Ray token when prompted) → **Cluster**: the
   rogueone node (`192.168.1.230`, 32 CPUs) is present, head shows 0 CPUs. After submitting (CLI below), watch
   **Jobs** / live Tune trials + per-trial logs.
3. **Register** — open `https://mlflow.weyland.lab` → experiment **`genre-classifier`**: one run per Tune trial
   (params + `f1_macro`); **Models → `genre_classifier`** shows the new registered version (the sweep winner).
4. **Consume** — no standing serving UI; the load-and-score is the CLI leg below.

## CLI walkthrough

Kubectl runs on **mother**; the worker is `rogueone`.

**Step 0 — worker joined + MLflow reachable:**
```
[rogueone] systemctl status ray-worker --no-pager
[mother] curl -s http://192.168.1.243:30500/health ; echo
```

**Step 1 — build the point-in-time training set from Feast** (leakage-free, in-cluster meshed bridge):
```
[mother] kubectl -n weyland exec deploy/dagster-user-code -- dagster asset materialize --select genre_feast_training_set -m weyland_pipeline.definitions
```

**Step 2 — submit the HP sweep to the persistent cluster** (trials run on rogueone; ~24 comparable runs + 1
registered winner):
```
[mother] kubectl -n weyland exec deploy/ray-head -- ray job submit --address http://localhost:8265 -- python /home/ray/train_genre.py --source feast --tune --trials 24
```
> `--source feast` trains from Feast's point-in-time features (the `genre_feast_training_set` parquet from
> Step 1). Same features → ~same accuracy as `--source silver` (v7 f1 ≈ 0.314); Feast buys point-in-time
> correctness + train/serve consistency, not a better model. Swap `--source silver` / `--source mart` per
> [remote-training.md](remote-training.md).

**Step 3 — confirm the registered version + artifact:**
```
[mother] kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'MLFLOW_TRACKING_URI=http://localhost:5000 mlflow models get-latest-versions --name genre_classifier' 2>/dev/null || echo "use the UI: Models → genre_classifier"
[mother] mc ls --recursive weyland/mlflow/genre-classifier/
```
> `TODO: verify` the exact `mlflow models` subcommand on the pinned MLflow 3.14 CLI; the always-available check is
> the UI (Models → `genre_classifier` → versions) and the MinIO listing above.

**Step 4 — SERVE / CONSUME the registered model (the missing leg).**
Load `models:/genre_classifier/latest` from the registry and score a sample. Run it from the **ray-head** pod,
which carries the trainer deps (scikit-learn), `mlflow==3.14.0`, and the platform env (MLflow tracking + MinIO
endpoint + creds + `AWS_CA_BUNDLE`) — the same env that registered the model:
```
[mother] kubectl -n weyland exec deploy/ray-head -- python - <<'PY'
import os, mlflow
# Head env already carries MLFLOW_TRACKING_URI + S3 endpoint/creds + AWS_CA_BUNDLE (parity with the trainer).
m = mlflow.pyfunc.load_model("models:/genre_classifier/latest")
# One sample row of the audio-feature vector the trainer fit on (order per train_genre.py feature list):
import pandas as pd
sample = pd.DataFrame([{
    "danceability":0.65,"energy":0.80,"loudness":-5.0,"speechiness":0.05,
    "acousticness":0.10,"instrumentalness":0.00,"liveness":0.12,"valence":0.55,"tempo":120.0
}])
print("prediction:", m.predict(sample))
PY
```
> `TODO: verify` the **exact feature column names + order** against `train_genre.py`'s feature list (the values
> above are an illustrative audio-feature row) — a column mismatch is the only thing that fails this leg. There is
> **no standing MLflow serving deployment** for `genre_classifier`; the REST-endpoint form
> (`mlflow models serve -m models:/genre_classifier/latest -p <port>` → `POST /invocations`) is the same model
> behind an HTTP surface, but it is **not currently deployed** — treat it as the follow-up, not a live endpoint.

## Expected result

- **Features:** `genre_feast_training_set` materializes to lakeFS `music/parquet/genre_feast_training/` (point-in-
  time, each row joined as of its own timestamp — no leakage).
- **Train:** the Ray job completes; the dashboard shows ~24 Tune trials on the rogueone worker.
- **Register:** MLflow experiment `genre-classifier` gains N trial runs + **1** new registered `genre_classifier`
  version; the winner's `model.pkl` is in `s3://mlflow/genre-classifier/…`. Measured baseline: single fit
  `acc ≈ 0.321 / f1_macro ≈ 0.305`; a 24-trial sweep beats it (best `f1 ≈ 0.308 / acc ≈ 0.327`).
- **Consume:** `mlflow.pyfunc.load_model("models:/genre_classifier/latest")` resolves the artifact from MinIO and
  `predict(sample)` returns a genre label — proof the registered version is a **loadable, scoring model**, closing
  the lifecycle from raw silver to a live prediction.

## Cleanup / teardown

The **consume** leg (Step 4) is read-only — it loads and scores, creating nothing.

The **train + register** run creates real data (MLflow trial runs, a registered version, a MinIO artifact). To
remove a demo run's output, per [remote-training.md](remote-training.md):
```
[mother] kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'MLFLOW_TRACKING_URI=http://localhost:5000 mlflow models delete-version --name genre_classifier --version <N>'
```
> `mlflow models delete-version` is `TODO: verify` on the pinned 3.14 CLI; the always-available equivalent is the
> UI (Models → `genre_classifier` → version → **Delete**). Do **not** delete the whole `genre_classifier` model
> unless you intend to drop every version. Then GC orphaned artifacts (DB-URI form from the runbook):
```
[mother] kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'B="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@weyland-postgres.weyland.svc.cluster.local:5432/mlflow"; MLFLOW_TRACKING_URI=http://localhost:5000 mlflow gc --backend-store-uri "$B" --artifacts-destination s3://mlflow/'
```
The `genre_feast_training_set` parquet is idempotently overwritten per materialize — no accumulation. The Ray
worker + head are long-lived infrastructure — leave them running (jobs just queue when rogueone sleeps).
