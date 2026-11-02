# Task: a new service, store-scaler — wake or sleep a parked data store on request

**Repo:** this repository (a homelab platform). **Location:** create `nodes/mother/lab/weyland-platform/services/store-scaler/`.

**Purpose.** Several rarely used data stores run with 0 replicas until someone needs one. A Port self-service button
sends a request to this service, which scales the store's Deployment to 1 (wake) or 0 (sleep). Background: search
`docs/` for "store-scaler" and the parked stores.

**Interface (this is the contract the service is accepted against).**
- A Python FastAPI application in `app.py` at the service root, exposing the ASGI app as `app`.
- It talks to Kubernetes ONLY through the official client: at import time it calls
  `kubernetes.config.load_incluster_config()` and creates `kubernetes.client.AppsV1Api()`; scaling calls
  `patch_namespaced_deployment_scale(name=<store>, namespace=<NAMESPACE>, body={"spec": {"replicas": <0|1>}})`.
  `NAMESPACE` is a module-level constant.
- Allowed stores (the allowlist): `cockroachdb`, `mongodb`, `mysql`, `gizmosql` by default, overridable by a
  comma-separated env var. Deployment name = store name. `NAMESPACE` defaults to `"data-mesh"`, also env-overridable.
- `GET /healthz` → `200 {"ok": true}`.
- `POST /scale` with a JSON body. The body is either a simple object `{"store": ..., "replicas": 0|1}` or
  `{"store": ..., "action": "wake"|"sleep"}`, or a Port polling payload in which an object containing BOTH `store` and
  `action` is nested at any depth.
  - success → `200 {"store": <store>, "namespace": <NAMESPACE>, "replicas": <0|1>, "status": "woke"|"slept"}`, after the
    scale call has been made with `replicas` 1 for wake and 0 for sleep;
  - store not on the allowlist → `400`, and the `detail` mentions the `allowlist`;
  - an `action` other than wake/sleep → `400`, `detail` contains `must be one of`;
  - `replicas` other than 0 or 1 → `400`, `detail` contains `0 (sleep) or 1 (wake)`;
  - neither `replicas` nor `action` given → `400`, `detail` contains `need replicas`.
  No scale call is made for any rejected request.
- `requirements.txt` with exact pins, a `Dockerfile` (non-root), and unit tests that run without a cluster (stub the
  kubernetes module).

**Acceptance criteria.**
- [ ] Every interface rule above holds, checked over HTTP with the Kubernetes client stubbed.
- [ ] The service's own tests pass with `python -m pytest` from the service directory.
- [ ] The Dockerfile builds a non-root image.

**Tools available on PATH:** `python3` with `fastapi`, `httpx`, `pytest` (a venv), `pip`.
