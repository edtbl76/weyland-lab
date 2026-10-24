# Demo — MLflow Experiment Tracking

MLflow (`mlflow.weyland.lab`, B10+B16) is the lab's experiment tracking + model registry. It reuses
the shared **Postgres** (backend store, `mlflow` db, STRICT mTLS — the pod is meshed) and **MinIO**
(`mlflow` bucket, artifact store). It's **two-plane**: run metadata (params / metrics / tags +
registry versions) goes **through** the server to Postgres; small artifacts proxy via
`--serve-artifacts`, but big models upload **direct to MinIO** (the experiment's
`artifact_location=s3://mlflow/…`) because the proxy times a multi-GB `model.pkl` out through the
1Gi pod. This demo logs a smoke run end-to-end (params + metric + artifact).

## Sequence diagram

Reuse the existing diagram: **[../diagrams/flow-mlflow.md](../diagrams/flow-mlflow.md)** (client →
Traefik/Keycloak or the LAN NodePort → MLflow server → Postgres metadata + MinIO artifacts →
run id + registered version).

## Prerequisites

- `mother` — hosts the MLflow deployment (`deploy/mlflow`, ns `weyland`), Postgres, and MinIO.
- Two access planes:
  - Browser / in-cluster: `https://mlflow.weyland.lab` (Keycloak forward-auth).
  - Programmatic / external (e.g. the rogueone Ray worker): the LAN NodePort
    `http://192.168.1.243:30500` (`mlflow-lan`, unauth, iptables-pinned to `rogueone`).
- For the direct artifact plane, clients need MinIO creds + `AWS_CA_BUNDLE` (mkcert root) to verify
  `s3.weyland.lab` TLS.
- Login: `emangini` / `weyland_dev_password`.

## UI walkthrough

1. Open `https://mlflow.weyland.lab` (Keycloak SSO).
2. **Experiments** → after running the smoke test below, select the **`smoke`** experiment; open
   the run and confirm the param `p=1`, metric `m=0.5`, and the artifact `a.txt`.
3. For the real ML workload, open the **`genre-classifier`** experiment — compare `accuracy` /
   `f1_macro` across runs and filter/group by the `feature_source` param; **Models** →
   **`genre_classifier`** lists the registered versions (see
   [../runbooks/mlflow-training.md](../runbooks/mlflow-training.md)).

## CLI walkthrough

Run the no-install smoke test inside the MLflow pod (logs a run against `localhost:5000`):

[mother] `kubectl exec -n weyland deploy/mlflow -- python -c "import mlflow; mlflow.set_tracking_uri('http://localhost:5000'); mlflow.set_experiment('smoke'); r=mlflow.start_run(); mlflow.log_param('p',1); mlflow.log_metric('m',0.5); open('/tmp/a.txt','w').write('hi'); mlflow.log_artifact('/tmp/a.txt'); mlflow.end_run(); print('OK', r.info.run_id)"`

Confirm the artifact landed in MinIO:

[mother] `mc ls --recursive weyland/mlflow/`

List experiments via the server's backend store (resolve the db creds from the mlflow secret):

[mother] `kubectl exec -n weyland deploy/mlflow -c mlflow -- sh -c 'MLFLOW_TRACKING_URI=http://localhost:5000 mlflow experiments search'`

## Expected result

- The smoke command prints `OK <run_id>`.
- A file appears under `mc ls --recursive weyland/mlflow/`.
- The `smoke` experiment + run (param `p`, metric `m`, artifact `a.txt`) is visible in the UI.
- `OK <run_id>` + the MinIO artifact + the run in the UI = the full stack (server + Postgres +
  MinIO) is healthy.

## RUN 2026-10-24 — the `weyland-mlflow` image (B227): nothing installed on start

The pod used to `pip install psycopg2-binary boto3 'mlflow[gateway]==3.16.1' litellm` (three unpinned) before every
start. It now runs `registry.weyland.lab/weyland-mlflow:git-bfa17089`: CI-built, signed, SBOM'd and trivy-scanned,
`FROM` the same 3.16.1 digest plus the pod's frozen `pip freeze` (`services/weyland-mlflow/`). Observed after Argo
rolled it (applied 20:24:37 UTC):

| Check | Result |
|---|---|
| Image / command | `weyland-mlflow:git-bfa17089`, 0 restarts; the container command contains no `pip` |
| Boot | pod start 20:25:05 → server up 20:25:24 → Ready 20:25:44 (39 s, 30 of them the probe's initial delay) |
| `pip freeze` in the pod | identical to `requirements.txt` (125 packages); `pip check`: no broken requirements |
| `mlflow db upgrade` | `Updating database tables`, no migration steps (a no-op on 3.16.1) |
| `:30500` | `GET /health` → `OK`; the AI Gateway lists **18** endpoints |
| Artifact round-trip | in the pod (this demo's smoke, plus a download): `OK`, `download: hi` |
| Gateway guardrails | `verify_gateway_guardrails.py` exit **2**: 0 FAIL on 7 local models, budget `$10 per 1 months, REJECT, GLOBAL`, PII redacted on all 7, the Safety guard blocked `unsafe-echo` on 6; the one REVIEW (`deepseek-coder-16b`) is a soft refusal |
| Ship transaction | `txn_mlflow` → `TXN_OK 18 gateway endpoint(s)` |

**Found on the way, pre-existing since 3.16.1 (B215), not caused by the image:** a download from OUTSIDE the
cluster (rogueone) hangs. A 3.16 server that proxies an S3 store advertises `multipart_downloads_enabled: true`
(`/api/3.0/mlflow/server-info`), so the client fetches the file from a presigned URL, and that URL names
`minio.minio.svc.cluster.local:9000`, which only resolves inside the cluster; the client retries about every 70 s.
The upload works (it is proxied). Off-cluster clients set `MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD=false` to stream
through the server instead: the same round-trip from rogueone then printed `ok` (runbook `mlflow.md` § Gotchas). No lab
code downloads artifacts from outside the cluster today.

## Cleanup / teardown

Delete the smoke experiment (removes its runs from the backend store), then garbage-collect the
artifacts. Grab the experiment id from the UI or `experiments search`, then, in the pod (the
`experiments delete` needs the DB URI; `gc` needs the **http** tracking URI to resolve artifacts):

[mother] `kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'B="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@weyland-postgres.weyland.svc.cluster.local:5432/mlflow"; MLFLOW_TRACKING_URI="$B" mlflow experiments delete --experiment-id <SMOKE_ID>; MLFLOW_TRACKING_URI=http://localhost:5000 mlflow gc --backend-store-uri "$B" --artifacts-destination s3://mlflow/'`

Optionally confirm the artifact was purged:

[mother] `mc ls --recursive weyland/mlflow/`

> Substitute `<SMOKE_ID>` with the `smoke` experiment id. Do **not** delete the `genre-classifier`
> experiment — it holds the real registered models.
