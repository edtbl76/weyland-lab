# The `weyland` realm + your single operator user. Realm-level SSO config lives here.
resource "keycloak_realm" "weyland" {
  realm        = "weyland"
  enabled      = true
  display_name = "Weyland"

  # SSO session lifetime — aligned at 10h, one sign-in per workday (2026-10-05, owner). The defaults were 30m idle /
  # 10h max; with a 30-minute IDLE limit, Open WebUI (whose own login lasted 4 weeks) refreshed its Keycloak token on
  # first use after a break, got `invalid_grant: Token is not active`, dropped the session and called the shared-memory
  # MCP tool with NO token — the gateway returned 401 and the chat model invented an answer. Idle = max = 10h ends a
  # session only at the cap; Open WebUI's JWT expiry is set to the same 10h (Admin → Settings → General) so its login
  # ends with the Keycloak session. Realm-wide on purpose: a client session cannot outlive the realm's idle timeout.
  sso_session_idle_timeout = "10h"
  sso_session_max_lifespan = "10h"
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
