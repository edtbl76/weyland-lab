# First OIDC client — Grafana (cleanest cutover; the proof before the fiddlier apps like MinIO).
# CONFIDENTIAL = Grafana holds a client secret (output below → drop into Grafana's generic_oauth config in Phase 3).
# NOTE: confirm grafana.weyland.lab is the real host; the redirect URI must match Grafana's /login/generic_oauth.
resource "keycloak_openid_client" "grafana" {
  realm_id  = keycloak_realm.weyland.id
  client_id = "grafana"
  name      = "Grafana"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  standard_flow_enabled = true # authorization-code flow

  valid_redirect_uris = ["https://grafana.weyland.lab/login/generic_oauth"]
  web_origins         = ["https://grafana.weyland.lab"]
}

output "grafana_client_secret" {
  value     = keycloak_openid_client.grafana.client_secret
  sensitive = true
}
