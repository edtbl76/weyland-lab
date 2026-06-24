# B1.1 — MinIO console OIDC client + a hardcoded `policy` claim so the SSO user gets MinIO's consoleAdmin policy.
resource "keycloak_openid_client" "minio" {
  realm_id  = keycloak_realm.weyland.id
  client_id = "minio"
  name      = "MinIO"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  standard_flow_enabled = true

  valid_redirect_uris = ["https://minio.weyland.lab/oauth_callback"]
  web_origins         = ["https://minio.weyland.lab"]
}

# MinIO reads MINIO_IDENTITY_OPENID_CLAIM_NAME=policy from the token → maps it to a MinIO policy. Hardcode
# policy=consoleAdmin for the solo operator (only you can auth through Keycloak, so blanket-admin is fine).
resource "keycloak_openid_hardcoded_claim_protocol_mapper" "minio_policy" {
  realm_id         = keycloak_realm.weyland.id
  client_id        = keycloak_openid_client.minio.id
  name             = "minio-policy"
  claim_name       = "policy"
  claim_value      = "consoleAdmin"
  claim_value_type = "String"
  add_to_id_token     = true
  add_to_access_token = true
  add_to_userinfo     = true
}

output "minio_client_secret" {
  value     = keycloak_openid_client.minio.client_secret
  sensitive = true
}
