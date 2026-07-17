# Flow — ML lifecycle end-to-end (silver → Feast → Ray train → MLflow register → serve/consume)

The full model lifecycle for the **`genre_classifier`**, threading four component flows plus the leg none of them
close — **consuming the registered model**. Feast serves the Spotify audio features point-in-time and the
in-cluster meshed bridge asset `genre_feast_training_set` does the leakage-free `get_historical_features` join to
lakeFS parquet ([flow-feast.md](flow-feast.md)); a Ray Tune HP sweep runs on the rogueone edge worker
([../demos/remote-training.md](../demos/remote-training.md)); the winner is registered as a new
`genre_classifier` version in MLflow, artifact PUT direct to MinIO ([flow-mlflow.md](flow-mlflow.md)); and the
missing leg loads `models:/genre_classifier/latest` back from the registry and scores a sample, proving the
registered artifact is a usable model, not just a catalog row. See [../demos/ml-lifecycle-e2e.md](../demos/ml-lifecycle-e2e.md).

**Current reality:** heavy training runs on **rogueone** (`192.168.1.230`, RTX 5000 Ada, 32 cores); weyland
(mother) is the control plane (MLflow tracking + registry, MinIO artifacts, lakeFS silver). The Ray head is a
coordinator (`--num-cpus=0`); trials schedule onto the rogueone worker. External clients reach MLflow via the LAN
NodePort `192.168.1.243:30500` (iptables-pinned to rogueone); MinIO TLS is verified via `AWS_CA_BUNDLE`.

## Sequence

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

Same features → ~same accuracy as `--source silver` (v7 f1 ≈ 0.314); Feast buys point-in-time correctness +
train/serve consistency, not a better model. The consume leg closes the lifecycle from raw silver to a live
prediction — a column mismatch against `train_genre.py`'s feature list is the only thing that fails it. There is
no standing MLflow serving deployment for `genre_classifier`; the REST-endpoint form is the same model behind an
HTTP surface, treated as the follow-up.
