# The `weyland` realm + your single operator user. Realm-level SSO config lives here.
resource "keycloak_realm" "weyland" {
  realm        = "weyland"
  enabled      = true
  display_name = "Weyland"
}

resource "keycloak_user" "operator" {
  realm_id       = keycloak_realm.weyland.id
  username       = "emangini"
  enabled        = true
  email          = "ed@timberbacklabs.com"
  first_name     = "Ed"
  last_name      = "Mangini"
  email_verified = true

  initial_password {
    value     = var.operator_password
    temporary = false
  }
}
