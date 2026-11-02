# Change request: store-scaler — a read-only status endpoint, and cassandra on the allowlist

**Repo:** this repository. **Service:** `nodes/mother/lab/weyland-platform/services/store-scaler/`.

**Background.** store-scaler wakes (replicas 1) or sleeps (replicas 0) an allowlisted parked data store through the
Kubernetes API (`POST /scale`). The Port button now needs to show a store's current state before acting.

**Required behaviour.**
1. Add `GET /status/{store}`. For an allowlisted store it reads the Deployment's scale with the official client,
   `AppsV1Api().read_namespaced_deployment_scale(name=<store>, namespace=<NAMESPACE>)`, and returns
   `200 {"store": <store>, "namespace": <NAMESPACE>, "replicas": <the scale's spec.replicas>}`. For a store not on the
   allowlist it returns `400` with a `detail` that mentions the `allowlist`. It never changes replicas.
2. Add `cassandra` to the DEFAULT allowlist (it stays env-overridable).
3. Everything `POST /scale` and `GET /healthz` did before still holds.
4. Add tests for the new endpoint (still runnable without a cluster).

**Acceptance criteria.**
- [ ] `GET /status/mysql` returns the store's replicas read from the scale API, with no scale write.
- [ ] `GET /status/<off-allowlist>` returns 400 mentioning the allowlist.
- [ ] `cassandra` can be woken and its status read; every earlier `/scale` and `/healthz` behaviour is unchanged.
- [ ] The service's own tests pass with `python -m pytest` from the service directory.

**Tools available on PATH:** `python3` with `fastapi`, `httpx`, `pytest` (a venv), `pip`.
