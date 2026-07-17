# MLflow — runbook (B10+B16)

Experiment tracking + model registry at `mlflow.weyland.lab` (Keycloak SSO via `traefik-forward-auth`). Reuses the shared **Postgres**
(backend store) and **MinIO** (artifact store — **two-plane**: small artifacts proxied, big models direct) — fits the lab's reuse ethos.

> **B47 upgrade (2.18 → 3.14).** MLflow 3.x replaces the Flask/gunicorn server with **FastAPI/uvicorn**.
> The Postgres backend schema was migrated with **`mlflow db upgrade <backend-store-uri>`** (run once
> against the `mlflow` db). The 3.x server needs an explicit **`--allowed-hosts`** (host allow-list; set
> to the LAN/ingress hosts or the API 400s on `Host`), and the pod memory `limits` were raised to **4Gi**
> (3.x boots heavier — the old 1Gi OOM'd on start).

- Manifest: `k8s/mlflow/mlflow.yaml` (Middleware + Deployment + Service + Ingress).
- Backend store: Postgres `mlflow` db owned by the `mlflow` role.
- Artifact store: MinIO `mlflow` bucket. **Two-plane:** small artifacts proxy **through** MLflow (`--serve-artifacts`); **big models upload DIRECT to MinIO** (experiment `artifact_location=s3://mlflow/…`) because the proxy times a multi-GB `model.pkl` out through the 1Gi pod. See [remote-training.md](remote-training.md) / [mlflow-training.md](mlflow-training.md).
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
  `FROM ghcr.io/mlflow/mlflow:v3.14.0` + `pip install` image and drop the install from the command.
- **No native auth** — access is gated by **Keycloak SSO** via the shared `traefik-forward-auth` Middleware
  (forward-auth → Keycloak, SSO across `*.weyland.lab`), like Kiali. The old `mlflow-auth` basicAuth dev-password
  Middleware is retired/superseded by the forward-auth gate.
- **Clients:** browser UI = `https://mlflow.weyland.lab` (Keycloak SSO). **Programmatic clients can't use the SSO
  ingress** (forward-auth is browser-only) → they use the **LAN NodePort**
  `MLFLOW_TRACKING_URI=http://192.168.1.243:30500` (`mlflow-lan`, unauth). The two-plane artifact path means
  clients **do** need MinIO creds + `AWS_CA_BUNDLE` (mkcert root) for the direct upload to `s3.weyland.lab`.
- **LAN NodePort (`mlflow-lan`, :30500).** Added for the external Ray training worker (svc DNS is cluster-only,
  the ingress is browser-SSO). Unauthenticated MLflow API on the LAN — `externalTrafficPolicy: Local` preserves
  the source IP so a host firewall can pin it to the worker: `sudo iptables -I INPUT 1 -p tcp --dport 30500 ! -s
  192.168.1.230 -j DROP` (on mother; not yet reboot-persistent). See [remote-training.md](remote-training.md).
