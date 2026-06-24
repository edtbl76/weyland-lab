# B1.1 — Open WebUI OIDC client. App side is pure env (clean, unlike GlitchTip's allauth).
# Redirect = WEBUI_URL + /oauth/oidc/callback. If login bounces with invalid_redirect, widen to chat.weyland.lab/*.
resource "keycloak_openid_client" "open_webui" {
  realm_id  = keycloak_realm.weyland.id
  client_id = "open-webui"
  name      = "Open WebUI"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  standard_flow_enabled = true

  valid_redirect_uris = ["https://chat.weyland.lab/oauth/oidc/callback"]
  web_origins         = ["https://chat.weyland.lab"]
}

output "open_webui_client_secret" {
  value     = keycloak_openid_client.open_webui.client_secret
  sensitive = true
}
