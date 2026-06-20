# MLflow — runbook (B10+B16)

Experiment tracking + model registry at `mlflow.weyland.lab` (dev-password). Reuses the shared **Postgres**
(backend store) and **MinIO** (artifact store, proxied) — fits the lab's reuse ethos.

- Manifest: `k8s/mlflow/mlflow.yaml` (Middleware + Deployment + Service + Ingress).
- Backend store: Postgres `mlflow` db owned by the `mlflow` role.
- Artifact store: MinIO `mlflow` bucket, served **through** MLflow (`--serve-artifacts`) so clients never touch MinIO directly.
- **Meshed:** the pod carries `sidecar.istio.io/inject: "true"` — STRICT-mTLS Postgres resets a non-meshed client (`read ECONNRESET`). See [[postgres-strict-needs-mesh]].

## Deploy (first time)
Postgres db + role, secrets, bucket, then apply:
```
kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -c "CREATE ROLE mlflow LOGIN PASSWORD 'weyland_dev_password';"
kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -c "CREATE DATABASE mlflow OWNER mlflow;"
kubectl create secret generic mlflow-secret -n weyland --from-literal=POSTGRES_USER=mlflow --from-literal=POSTGRES_PASSWORD=weyland_dev_password
kubectl create secret generic mlflow-auth -n weyland --from-literal=users="admin:$(openssl passwd -apr1 weyland_dev_password)"
mc mb weyland/mlflow
kubectl apply -f k8s/mlflow/mlflow.yaml && kubectl rollout status deploy/mlflow -n weyland
```

## Smoke test (no installs)
```
kubectl exec -n weyland deploy/mlflow -- python -c "import mlflow; mlflow.set_tracking_uri('http://localhost:5000'); mlflow.set_experiment('smoke'); r=mlflow.start_run(); mlflow.log_param('p',1); mlflow.log_metric('m',0.5); open('/tmp/a.txt','w').write('hi'); mlflow.log_artifact('/tmp/a.txt'); mlflow.end_run(); print('OK', r.info.run_id)"
```
`OK <run_id>` + a file under `mc ls --recursive weyland/mlflow/` + the run in the UI = full stack good.

## Gotchas
- **pip-on-start (v1).** The container installs `psycopg2-binary` + `boto3` on every start (no custom image),
  so first/restart boot is ~1–2 min and needs egress. If restarts get slow/flaky, bake a small
  `FROM ghcr.io/mlflow/mlflow:v2.18.0` + `pip install` image and drop the install from the command.
- **No native auth** — the dev-password is a Traefik `basicAuth` Middleware (`mlflow-auth`), like Kiali/Jaeger.
- **Clients:** point `MLFLOW_TRACKING_URI=https://mlflow.weyland.lab` with `MLFLOW_TRACKING_USERNAME=admin` /
  `MLFLOW_TRACKING_PASSWORD=weyland_dev_password`. Proxied artifacts mean no MinIO creds needed client-side.
