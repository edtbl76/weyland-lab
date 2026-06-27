# Superset OIDC client (B65 Tier-2). CONFIDENTIAL → holds a client secret (output below → superset_config.py).
# Redirect URI is Flask-AppBuilder's OAuth callback: /oauth-authorized/<provider_name>, provider = "keycloak".
resource "keycloak_openid_client" "superset" {
  realm_id  = keycloak_realm.weyland.id
  client_id = "superset"
  name      = "Superset"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  standard_flow_enabled = true # authorization-code flow

  valid_redirect_uris = ["https://superset.weyland.lab/oauth-authorized/keycloak"]
  web_origins         = ["https://superset.weyland.lab"]
}

output "superset_client_secret" {
  value     = keycloak_openid_client.superset.client_secret
  sensitive = true
}

# NOTE — admin grant is handled in superset_config.py via AUTH_USER_REGISTRATION_ROLE = "Admin": for a solo
# lab behind the Keycloak gate, the only OIDC user (emangini) lands as Admin. Provider v5.8.0's
# keycloak_user_roles is authoritative-only (would wipe a user's other realm roles), so role-based mapping
# (a Superset_Admin role + AUTH_ROLES_MAPPING) is deferred to a multi-user upgrade (needs a provider bump or
# an additive `kcadm add-roles`, not a one-shot tofu wipe).
