# DataHub OIDC client (B1.3). Redirect = the datahub-frontend OIDC callback path.
# CONFIDENTIAL → secret output below drops into the data-mesh `datahub-oidc` k8s secret (AUTH_OIDC_CLIENT_SECRET).
resource "keycloak_openid_client" "datahub" {
  realm_id  = keycloak_realm.weyland.id
  client_id = "datahub"
  name      = "DataHub"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  standard_flow_enabled = true # authorization-code flow

  valid_redirect_uris = ["https://datahub.weyland.lab/callback/oidc"]
  web_origins         = ["https://datahub.weyland.lab"]
}

output "datahub_client_secret" {
  value     = keycloak_openid_client.datahub.client_secret
  sensitive = true
}
