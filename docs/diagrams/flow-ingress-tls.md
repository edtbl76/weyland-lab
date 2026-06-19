# Flow: Ingress / TLS Front Door

The shared path for every `*.weyland.lab` UI. CoreDNS resolves the wildcard to mother; Traefik terminates
TLS with the mkcert wildcard cert (`weyland-wildcard-tls`); protected UIs add a basicAuth middleware; meshed
backends add an Envoy hop. Traefik is the *only* edge ingress — there is no Istio gateway.

```mermaid
sequenceDiagram
    participant Br as Browser
    participant DNS as CoreDNS (*.weyland.lab)
    participant Tr as Traefik (TLS termination)
    participant MW as Middleware (e.g. observability-auth basicAuth)
    participant Env as Envoy sidecar (if backend meshed)
    participant Svc as Service (Kiali / Grafana / Dagster / ...)
    Br->>DNS: resolve grafana.weyland.lab
    DNS-->>Br: mother IP
    Br->>Tr: HTTPS (SNI)
    Tr->>Tr: terminate TLS (weyland-wildcard-tls, mkcert)
    opt protected UI
        Tr->>MW: basicAuth (dev-password)
        MW-->>Tr: allow
    end
    Tr->>Env: route to backend service
    Env->>Svc: forward (plaintext on loopback)
    Svc-->>Br: response
```
