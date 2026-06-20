# Flow: MLflow tracking + artifacts (B10+B16)

A client (a training or eval run) logs to MLflow at `mlflow.weyland.lab`. Traefik gates with the dev-password
(`basicAuth` middleware), then proxies to the MLflow server. Run metadata (params/metrics/tags) goes to the
**Postgres** backend store over STRICT mTLS (the pod is meshed). Artifacts are uploaded **through** MLflow
(`--serve-artifacts`) to the **MinIO** `mlflow` bucket — clients never need MinIO creds. The model registry
versions live in the same Postgres store.

```mermaid
sequenceDiagram
    participant Cl as Client (training / eval)
    participant TR as Traefik (dev-password)
    participant ML as MLflow server (meshed)
    participant PG as Postgres (mlflow db, STRICT mTLS)
    participant S3 as MinIO (mlflow bucket)
    Cl->>TR: log run params/metrics (https mlflow.weyland.lab)
    TR->>ML: basic-auth OK, proxy
    ML->>PG: write run + params + metrics (backend store, mTLS)
    Cl->>TR: log artifact
    TR->>ML: proxy
    ML->>S3: PUT artifact (serve-artifacts proxy)
    ML-->>Cl: run_id + artifact URI
    Cl->>TR: register model version
    TR->>ML: proxy
    ML->>PG: write registered model + version (lineage)
```
