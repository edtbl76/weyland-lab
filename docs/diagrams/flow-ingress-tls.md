# Flow: Ingress / TLS Front Door

The shared path for every `*.weyland.lab` UI. CoreDNS resolves the wildcard to mother; Traefik terminates
TLS with the mkcert wildcard cert (`weyland-wildcard-tls`); protected UIs add the `traefik-forward-auth`
middleware (forward-auth → Keycloak SSO, was a basicAuth dev-password middleware); meshed backends add an
Envoy hop. Traefik is the *only* edge ingress — there is no Istio gateway. Single sign-on across
`*.weyland.lab` via `COOKIE_DOMAIN=weyland.lab`; single logout at `auth.weyland.lab/_oauth/logout`.

```mermaid
sequenceDiagram
    participant Br as Browser
    participant DNS as CoreDNS (*.weyland.lab)
    participant Tr as Traefik (TLS termination)
    participant FA as traefik-forward-auth Middleware
    participant KC as Keycloak (auth.weyland.lab)
    participant Env as Envoy sidecar (if backend meshed)
    participant Svc as Service (Kiali / Grafana / Dagster / ...)
    Br->>DNS: resolve grafana.weyland.lab
    DNS-->>Br: mother IP
    Br->>Tr: HTTPS (SNI)
    Tr->>Tr: terminate TLS (weyland-wildcard-tls, mkcert)
    opt protected UI (no valid session)
        Tr->>FA: forward-auth check
        FA-->>Br: 302 redirect to Keycloak
        Br->>KC: login (OIDC)
        KC-->>Br: 302 back with session cookie
        Br->>Tr: retry with cookie
        Tr->>FA: forward-auth check
        FA-->>Tr: allow (valid session)
    end
    Tr->>Env: route to backend service
    Env->>Svc: forward (plaintext on loopback)
    Svc-->>Br: response
```
