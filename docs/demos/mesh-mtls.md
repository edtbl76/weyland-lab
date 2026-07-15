# Demo — Service-Mesh mTLS (Istio)

How an in-cluster (east-west) call traverses the Istio sidecars, and how to prove mTLS is
enforced. Slice 1 is **PERMISSIVE** (accepts mTLS *and* plaintext); **Postgres is STRICT**
(plaintext rejected pre-auth). The app is unaware of the mesh — it calls localhost and Envoy
does the rest. Traefik stays the *edge* ingress; the mesh is east-west only. Istio 1.30.1,
Kiali v2.26. Meshed: tool-server + the 4 vector/graph backends (qdrant, weaviate, neo4j, Postgres).

## Sequence diagram

Reused from [../diagrams/flow-mesh-mtls.md](../diagrams/flow-mesh-mtls.md):

```mermaid
sequenceDiagram
    participant App as Client app (tool-server / Dagster)
    participant CE as Client Envoy (sidecar)
    participant SE as Server Envoy (sidecar)
    participant Svc as Backend (pgvector / qdrant / weaviate / neo4j)
    App->>CE: plaintext call to localhost (app unaware of mesh)
    CE->>SE: mTLS, SPIFFE identity (certs issued by istiod)
    Note over CE,SE: PERMISSIVE accepts mTLS or plaintext. STRICT (Postgres) requires mTLS
    SE->>Svc: plaintext handoff on loopback
    Svc-->>SE: response
    SE-->>CE: mTLS
    CE-->>App: response
    Note over SE: STRICT + un-meshed plaintext client -> Envoy resets pre-auth ("server closed the connection")
```

## Prerequisites
- Istio installed on mother's k3s (istiod, minimal profile — no Istio gateway).
- Kiali at `kiali.weyland.lab` (Keycloak SSO via forward-auth; read-only, `view_only_mode`).
- `istioctl` on mother's PATH (download matching the mesh version 1.30.1 if absent).
- Meshed workloads carry the pod **label** `sidecar.istio.io/inject: "true"` (the `weyland` ns is unlabeled, so the annotation is a no-op).

## UI walkthrough
1. Open `https://kiali.weyland.lab` (Keycloak login).
2. **Graph** → namespace `weyland` → **Display → Security**. Lock icons on the tool-server↔backend edges = mTLS.
3. Click a workload (e.g. `weyland-tool-server`) → **Traces** tab to see spans (Tempo-backed).
4. Confirm the Mesh view shows all components green (Kiali wired to Prometheus + Tempo + Grafana).

## CLI walkthrough
[mother] Confirm a meshed workload has its sidecar injected (2/2 = app + Envoy):
```
kubectl get pods -n weyland -l app=weyland-tool-server
```
[mother] Inspect per-pod mTLS status for a backend pod:
```
istioctl x describe pod $(kubectl get pod -n weyland -l app=weyland-postgres -o jsonpath='{.items[0].metadata.name}') -n weyland
```
[mother] No-regression check — the backend is still reachable end-to-end (PERMISSIVE):
```
curl -s http://mother:30080/status
```
[mother] **Prove STRICT enforces on Postgres** from an un-meshed pod (a bare `nc -z` is a false negative — use a real client). Enforcing = `server closed the connection unexpectedly` (Envoy resets pre-auth), NOT `password authentication failed`:
```
kubectl run pgtest --rm -i --image=postgres:16 -n default --restart=Never -- psql "postgresql://weyland:nope@weyland-postgres.weyland.svc.cluster.local:5432/weyland?sslmode=disable" -c "select 1"
```
[mother] Confirm a **meshed** client still reaches STRICT Postgres (both ends mTLS):
```
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import psycopg2,os; c=psycopg2.connect(host='weyland-postgres.weyland.svc.cluster.local',port=5432,dbname='weyland',user='weyland',password=os.environ['WEYLAND_PG_PASSWORD']); cur=c.cursor(); cur.execute('SELECT count(*) FROM rag_chunks'); print(cur.fetchone()[0])"
```

## Expected result
- `kubectl get pods` shows `2/2` for meshed workloads.
- Kiali graph shows lock icons (mTLS) on meshed edges.
- `/status` returns healthy — mesh is transparent to the app.
- The un-meshed `pgtest` connect is **reset pre-auth** (`server closed the connection unexpectedly`) = STRICT is enforcing.
- The meshed Dagster→Postgres query returns a row count = meshed clients keep working.

## Cleanup / teardown
- The `pgtest` pod uses `--rm` and auto-deletes when the command exits. If it lingers after an interrupt, remove it explicitly:
```
kubectl delete pod pgtest -n default --ignore-not-found
```
- Everything else is read-only (Kiali is `view_only_mode`, `istioctl x describe` and `/status` observe only).
