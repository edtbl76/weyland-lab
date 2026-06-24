# B1.1 — GlitchTip OIDC client. The APP side is wired via the Django admin (allauth "Social Application"),
# NOT env vars — see the runbook. allauth's OIDC callback path is /accounts/oidc/<provider_id>/login/callback/
# with provider_id = "keycloak" (the id you enter in the admin). If login bounces with "invalid redirect_uri",
# widen valid_redirect_uris to "https://glitchtip.weyland.lab/*".
resource "keycloak_openid_client" "glitchtip" {
  realm_id  = keycloak_realm.weyland.id
  client_id = "glitchtip"
  name      = "GlitchTip"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  standard_flow_enabled = true

  valid_redirect_uris = ["https://glitchtip.weyland.lab/accounts/oidc/keycloak/login/callback/"]
  web_origins         = ["https://glitchtip.weyland.lab"]
}

output "glitchtip_client_secret" {
  value     = keycloak_openid_client.glitchtip.client_secret
  sensitive = true
}
