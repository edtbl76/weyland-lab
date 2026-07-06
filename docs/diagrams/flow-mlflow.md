# Flow: MLflow tracking + artifacts (B10+B16) — two-plane

A client (a training or eval run) logs to MLflow. **Two access planes:** browser / in-cluster clients hit
`mlflow.weyland.lab` (Traefik + Keycloak `traefik-forward-auth`); the **external Ray worker** (rogueone) hits the
**LAN NodePort `192.168.1.243:30500`** (`mlflow-lan`, unauth, `externalTrafficPolicy: Local`, iptables-pinned to
rogueone) — the SSO ingress is browser-only and svc DNS is cluster-only. **Two data planes:** run metadata
(params / metrics / tags + registry versions) → **Postgres** over STRICT mTLS (the pod is meshed); **artifacts** —
small ones can proxy via `--serve-artifacts`, but **big models upload DIRECT to MinIO** (the experiment's
`artifact_location=s3://mlflow/…`) because the serve-artifacts proxy times a multi-GB `model.pkl` out through the
1Gi MLflow pod. The external worker's TLS to MinIO (`s3.weyland.lab`) is verified via `AWS_CA_BUNDLE` (mkcert root).

```mermaid
sequenceDiagram
    participant Cl as Client (in-cluster / browser)
    participant Wk as Ray worker (rogueone, external)
    participant TR as Traefik (forward-auth → Keycloak)
    participant NP as NodePort mlflow-lan (:30500)
    participant ML as MLflow server (meshed)
    participant PG as Postgres (mlflow db, STRICT mTLS)
    participant S3 as MinIO (mlflow bucket)
    Cl->>TR: log run params/metrics (https mlflow.weyland.lab)
    TR->>ML: forward-auth (Keycloak) OK, proxy
    Wk->>NP: log run params/metrics (http :30500, unauth LAN)
    NP->>ML: proxy
    ML->>PG: write run + params + metrics (backend store, mTLS)
    Wk->>S3: PUT model artifact DIRECT (s3://mlflow/…, TLS via AWS_CA_BUNDLE)
    ML->>PG: write registered model + version (lineage)
    ML-->>Cl: run_id + artifact URI
    ML-->>Wk: run_id + registered version
```
