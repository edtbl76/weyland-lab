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

# Realm role → mapped to Superset's built-in "Admin" via AUTH_ROLES_MAPPING in superset_config.py.
resource "keycloak_role" "superset_admin" {
  realm_id = keycloak_realm.weyland.id
  name     = "Superset_Admin"
}

# Put the user's realm roles into a "roles" claim so Superset's custom SECURITY_MANAGER can read them
# (Keycloak doesn't surface realm roles to the userinfo endpoint without this mapper).
resource "keycloak_openid_user_realm_role_protocol_mapper" "superset_roles" {
  realm_id    = keycloak_realm.weyland.id
  client_id   = keycloak_openid_client.superset.id
  name        = "realm-roles"
  claim_name  = "roles"
  multivalued = true
}

# emangini → Superset_Admin. exclusive=false is CRITICAL: additive, so this never wipes emangini's other realm roles.
data "keycloak_user" "emangini" {
  realm_id = keycloak_realm.weyland.id
  username = "emangini"
}

resource "keycloak_user_roles" "emangini_superset_admin" {
  realm_id  = keycloak_realm.weyland.id
  user_id   = data.keycloak_user.emangini.id
  role_ids  = [keycloak_role.superset_admin.id]
  exclusive = false
}

output "superset_client_secret" {
  value     = keycloak_openid_client.superset.client_secret
  sensitive = true
}
