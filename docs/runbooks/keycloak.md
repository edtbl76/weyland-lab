# Keycloak — the lab IdP / SSO (B1.1)

**What:** Keycloak is the single identity provider for every `*.weyland.lab` browser UI. One realm (`weyland`),
one operator user, and two ways apps consume it: **native OIDC** (the app speaks OpenID Connect itself —
Grafana, DataHub, Superset, GlitchTip, JupyterHub, Open-WebUI) and **forward-auth** (a Traefik gate in front of
apps that have no OIDC of their own — MLflow, NeoDash, Kiali, Ranger, Nessie, Cube, Gatekeeper Policy Manager,
…). Every gated UI ultimately bounces through here.

**Where:**
- UI / issuer: **https://keycloak.weyland.lab** (Keycloak IS the auth — its ingress carries **no** forward-auth
  middleware). Realm issuer: `https://keycloak.weyland.lab/realms/weyland`.
- Forward-auth host: **https://auth.weyland.lab** (the central callback for the forward-auth gate; see below).
- In-cluster: `keycloak.weyland.svc.cluster.local:8080` (HTTP — Traefik terminates TLS).
- Manifests: `k8s/keycloak/keycloak.yaml` (server) · `k8s/traefik-forward-auth/traefik-forward-auth.yaml`
  (the SSO gate). Secrets: the `*-secret.example.yaml` siblings (real Secrets created out-of-band, never committed).
- Realm + clients as code: `tofu/keycloak/` (`realm.tf`, `main.tf`, one `*.tf` per OIDC client). State in MinIO.
- **Creds:** bootstrap admin from `keycloak-secret` (`KC_BOOTSTRAP_ADMIN_USERNAME`/`_PASSWORD`); realm operator
  user `emangini` (password = the shared dev cred, [[lab-dev-credentials]]). See [[keycloak-sso-b1.1]].

## Architecture

Raw `Deployment` (chosen over Operator/Helm to fit the Argo raw-manifest pattern), `quay.io/keycloak/keycloak:26.1.0`,
ns `weyland`, `strategy: Recreate` (single instance on a shared DB — never race two pods on the schema/build).
Store = the shared **weyland-postgres** (`keycloak` DB); Postgres is **STRICT mTLS**, so the pod carries
`sidecar.istio.io/inject: "true"` — without the mesh sidecar the JDBC connection resets ([[postgres-strict-needs-mesh]]).
Runs `kc.sh start` in production/proxy mode: `KC_PROXY_HEADERS=xforwarded` + `KC_HTTP_ENABLED=true` (Traefik does
TLS), `KC_HOSTNAME=https://keycloak.weyland.lab`. Health + metrics on the **management port 9000** (`/health/ready`,
`/health/live`) — KC 25+ moved these off the HTTP port.

**The `weyland` realm + OIDC clients are code** (`tofu/keycloak/`, provider `keycloak/keycloak ~> 5.0`). OpenTofu
runs from **rogueone** against the live server (`admin-cli`, creds via env — nothing committed), TLS verified
against rogueone's system trust store (the mkcert root is installed there). State in MinIO (`s3.weyland.lab`,
`tofu-state`, key `keycloak/terraform.tfstate`).

## The two SSO patterns

**1. Native OIDC** — the app holds a client secret and does the auth-code dance itself. Each client is a
`keycloak_openid_client` (`access_type = CONFIDENTIAL`, `standard_flow_enabled = true`) with `valid_redirect_uris`
= the app's own callback (e.g. DataHub `https://datahub.weyland.lab/callback/oidc`, Grafana
`https://grafana.weyland.lab/login/generic_oauth`). `tofu apply` outputs the client secret (`sensitive`) which
drops into that app's k8s Secret. Pattern files: `tofu/keycloak/{grafana,datahub,superset,glitchtip,jupyterhub,open-webui}.tf`.

**2. Forward-auth (auth-host mode)** — for UIs with no native OIDC. A single `traefik-forward-auth` Deployment
(`thomseddon/traefik-forward-auth:2`, ns `weyland`) is the **one** OIDC client for **all** gated subdomains:
- `AUTH_HOST=auth.weyland.lab` + `COOKIE_DOMAIN=weyland.lab` → **one** client, **one** redirect URI
  (`https://auth.weyland.lab/_oauth`), and the cookie is valid across every `*.weyland.lab` subdomain = SSO
  everywhere. The client (`tofu/keycloak/traefik-forward-auth.tf`) has exactly that one `valid_redirect_uri`.
- A Traefik `forwardAuth` **Middleware** (`weyland-traefik-forward-auth@kubernetescrd`) fronts each protected
  ingress. Cross-namespace refs work (Kiali's ingress in `istio-system` references the `weyland` one directly).
- **Logout:** hit `https://auth.weyland.lab/_oauth/logout` — it clears the forward-auth cookie **and** bounces to
  Keycloak's end-session endpoint (`LOGOUT_REDIRECT`) to kill the SSO session too (else the next app silently re-auths).

## The mkcert CA-bundle back-channel

`*.weyland.lab` uses a **mkcert** wildcard cert. Anything that talks to `keycloak.weyland.lab` over the
**back-channel** (server-to-server, no browser trust store) must trust that mkcert root:
- **forward-auth** mounts the `weyland-mkcert-ca` Secret and sets `SSL_CERT_FILE=/mkcert/rootCA.pem`. Go trusts
  *only* that one CA — fine, since Keycloak is its sole HTTPS target.
- **JVM apps** (e.g. DataHub frontend) need a full truststore = system `cacerts` **+** the mkcert root, built by an
  initContainer (`keytool -importcert … rootCA.pem`) and passed via `JAVA_TOOL_OPTIONS`. See [datahub.md](datahub.md).

If a back-channel client throws `PKIX`/`x509 unknown authority` reaching Keycloak, its truststore is missing the
mkcert root. (For OpenTofu on rogueone: `mkcert -install` to re-add the root to the system store.)

## Adding a new gated subdomain

For a **forward-auth** app (no Keycloak change needed — the one client already covers every subdomain):
1. DNS: add the subdomain to LAN DNS + your `/etc/hosts` (LAN-only lab); for in-cluster resolution add it to the
   `coredns-custom` ConfigMap ([[coredns-cluster-lan-resolution]]).
2. Ingress: TLS via `secretName: weyland-wildcard-tls`, and annotate the router:
   `traefik.ingress.kubernetes.io/router.middlewares: weyland-traefik-forward-auth@kubernetescrd`.
3. **If the app's namespace can't reference the `weyland` middleware** (some Traefik setups block the cross-ns ref,
   and apps that also need an https-upgrade chain it locally), create **local copies** of the `forwardAuth` (and
   `redirectScheme: https`) Middlewares in the app's namespace and chain them — see `k8s/gatekeeper/policy-manager.yaml`
   and `k8s/data-mesh/ranger.yaml` for the pattern.

For a **native-OIDC** app: add a `keycloak_openid_client` in `tofu/keycloak/<app>.tf` with the app's callback as
`valid_redirect_uris`, `tofu apply`, then wire the output client secret into the app's Secret + OIDC env.

## Common admin ops (on **mother**)

Read the bootstrap admin password:
```
kubectl -n weyland get secret keycloak-secret -o jsonpath='{.data.KC_BOOTSTRAP_ADMIN_PASSWORD}' | base64 -d; echo
```
Restart (config env change — Recreate rolls cleanly):
```
kubectl -n weyland rollout restart deploy/keycloak
```
Reconcile realm + clients from code (on **rogueone**, in `tofu/keycloak/`):
```
tofu plan     # dry-run against the live server
tofu apply    # then wire any new client secret into the app's k8s Secret
```

## Gotchas

- **Meshed, or Postgres resets the JDBC connection.** The `sidecar.istio.io/inject` label is load-bearing
  ([[postgres-strict-needs-mesh]]).
- **`start` auto-builds providers on boot** (~30-60s slower start). If restart latency bites, bake a
  `kc.sh build` + `start --optimized` image (same note as MLflow).
- **KC 26 renamed the bootstrap-admin envs** `KEYCLOAK_ADMIN*` → `KC_BOOTSTRAP_ADMIN_*`.
- **Verify a freshly-created Secret round-trips** (base64-decode it) before restart — paste-mangling has injected
  invisible chars into other lab Secrets ([[feedback-verify-secret-after-create]]).
- **`http://` redirect downgrade** bites forward-auth apps whose own Tomcat ignores `X-Forwarded-Proto`
  (Ranger) — chain a `redirectScheme: https` Middleware **before** forward-auth so Keycloak sees an `https`
  `redirect_uri`. See [ranger.md](ranger.md).

## Links
- [[keycloak-sso-b1.1]] · [[postgres-strict-needs-mesh]] · [[coredns-cluster-lan-resolution]] ·
  [[lab-dev-credentials]] · [datahub.md](datahub.md) · [ranger.md](ranger.md) · [opentofu.md](opentofu.md)
