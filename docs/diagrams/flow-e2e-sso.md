# Flow (E2E) — SSO: browser → Traefik → forward-auth → Keycloak → app (one login, every subdomain)

Cross-system thread of [flow-ingress-tls](flow-ingress-tls.md) and the Keycloak runbook
([../runbooks/keycloak.md](../runbooks/keycloak.md)): the first hit on a gated `*.weyland.lab` UI bounces through
Keycloak once; the forward-auth cookie (`COOKIE_DOMAIN=weyland.lab`) then covers **every** subdomain, so a second
gated app needs no second login. Demo: [../demos/sso-e2e.md](../demos/sso-e2e.md).

```mermaid
sequenceDiagram
    participant Br as Browser
    participant DNS as CoreDNS<br/>(*.weyland.lab → mother)
    participant Tr as Traefik<br/>(TLS termination)
    participant FA as traefik-forward-auth<br/>(auth.weyland.lab, one OIDC client)
    participant KC as Keycloak<br/>(keycloak.weyland.lab, realm weyland)
    participant A1 as App 1 (grafana)
    participant A2 as App 2 (kiali / dagster)

    Br->>DNS: resolve grafana.weyland.lab
    DNS-->>Br: mother IP (192.168.1.243)
    Br->>Tr: HTTPS (SNI)
    Tr->>Tr: terminate TLS (weyland-wildcard-tls, mkcert)
    Tr->>FA: forward-auth check (no session)
    FA-->>Br: 302 → Keycloak (redirect_uri auth.weyland.lab/_oauth)
    Br->>KC: OIDC login (emangini)
    KC-->>Br: 302 back + session cookie (domain weyland.lab)
    Br->>Tr: retry with cookie
    Tr->>FA: forward-auth check → allow
    Tr->>A1: route to backend
    A1-->>Br: response (first UI)
    Note over Br,A2: second gated subdomain — cookie already valid
    Br->>Tr: GET kiali.weyland.lab (same cookie)
    Tr->>FA: forward-auth check → allow (no re-login)
    Tr->>A2: route to backend
    A2-->>Br: response (SSO — zero prompts)
```

**Seams made explicit:** ingress/TLS owns DNS → Traefik → cert → middleware ([ingress-tls](../demos/ingress-tls.md));
Keycloak owns the realm + the single forward-auth client whose one redirect URI + `weyland.lab` cookie make SSO
work across subdomains ([keycloak runbook](../runbooks/keycloak.md)). Single logout for all:
`https://auth.weyland.lab/_oauth/logout`.
