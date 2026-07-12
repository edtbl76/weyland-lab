# OIDC client — JupyterHub (B1.8 L8). CONFIDENTIAL: the hub holds a client secret (output below → drop into the
# Z2JH values `hub.config.GenericOAuthenticator.client_secret`, via a k8s Secret). Redirect URI is JupyterHub's
# OAuth callback (/hub/oauth_callback). Per-user identity comes from this OIDC login (not forward-auth).
resource "keycloak_openid_client" "jupyterhub" {
  realm_id  = keycloak_realm.weyland.id
  client_id = "jupyterhub"
  name      = "JupyterHub"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  standard_flow_enabled = true # authorization-code flow

  valid_redirect_uris = ["https://jupyter.weyland.lab/hub/oauth_callback"]
  web_origins         = ["https://jupyter.weyland.lab"]
}

output "jupyterhub_client_secret" {
  value     = keycloak_openid_client.jupyterhub.client_secret
  sensitive = true
}
