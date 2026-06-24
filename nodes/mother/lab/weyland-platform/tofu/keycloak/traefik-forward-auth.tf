# B1.1 — traefik-forward-auth client (forward-auth SSO gate for MLflow/NeoDash/Kiali + any future *.weyland.lab
# UI with no native OIDC). Central auth host: ONE redirect URI covers every subdomain (COOKIE_DOMAIN=weyland.lab).
resource "keycloak_openid_client" "traefik_forward_auth" {
  realm_id  = keycloak_realm.weyland.id
  client_id = "traefik-forward-auth"
  name      = "Traefik Forward Auth"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  standard_flow_enabled = true

  valid_redirect_uris = ["https://auth.weyland.lab/_oauth"]
  web_origins         = ["https://auth.weyland.lab"]
}

output "traefik_forward_auth_client_secret" {
  value     = keycloak_openid_client.traefik_forward_auth.client_secret
  sensitive = true
}
