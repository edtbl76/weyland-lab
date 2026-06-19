# Flow: Service-Mesh Request Path + mTLS (B8)

How an in-cluster (east-west) call traverses the Istio sidecars. Slice 1 is **PERMISSIVE** (accepts mTLS
*and* plaintext); **Postgres is STRICT** (plaintext rejected pre-auth). The app is unaware of the mesh — it
calls localhost and Envoy does the rest. Traefik stays the *edge* ingress; the mesh is east-west only.
TCP backends (neo4j Bolt, Postgres) need `appProtocol: tcp` or Envoy mis-parses them as HTTP.

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
