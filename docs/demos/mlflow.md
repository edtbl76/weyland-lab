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

## Cleanup / teardown

Delete the smoke experiment (removes its runs from the backend store), then garbage-collect the
artifacts. Grab the experiment id from the UI or `experiments search`, then, in the pod (the
`experiments delete` needs the DB URI; `gc` needs the **http** tracking URI to resolve artifacts):

[mother] `kubectl -n weyland exec deploy/mlflow -c mlflow -- sh -c 'B="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@weyland-postgres.weyland.svc.cluster.local:5432/mlflow"; MLFLOW_TRACKING_URI="$B" mlflow experiments delete --experiment-id <SMOKE_ID>; MLFLOW_TRACKING_URI=http://localhost:5000 mlflow gc --backend-store-uri "$B" --artifacts-destination s3://mlflow/'`

Optionally confirm the artifact was purged:

[mother] `mc ls --recursive weyland/mlflow/`

> Substitute `<SMOKE_ID>` with the `smoke` experiment id. Do **not** delete the `genre-classifier`
> experiment — it holds the real registered models.
