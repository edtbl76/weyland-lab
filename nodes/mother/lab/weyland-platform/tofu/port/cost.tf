# Port `cost` blueprint (B55) — the 7th blueprint (the generated blueprints.tf covers the other 6).
# No `provider =` line (that's the bug that caused the phantom hashicorp/port-labs); resolves via the
# `port_` prefix → the `port` provider mapped in main.tf. Brought into state with CLI `tofu import`.
resource "port_blueprint" "cost" {
  identifier            = "cost"
  title                 = "Recurring Cost"
  icon                  = "Cost"
  create_catalog_page   = true
  force_delete_entities = false
  properties = {
    number_props = {
      "amount" = { title = "Amount (USD)", required = false }
    }
    string_props = {
      "category" = {
        title    = "Category"
        required = false
        enum     = ["infra", "ai", "dev-tools", "domain", "business", "other"]
        enum_colors = {
          infra       = "blue"
          ai          = "purple"
          "dev-tools" = "orange"
          domain      = "green"
          business    = "red"
          other       = "lightGray"
        }
      }
      "vendor" = { title = "Vendor", required = false }
      "cadence" = {
        title    = "Billing Cadence"
        required = false
        enum     = ["monthly", "annual", "one-time"]
        enum_colors = {
          monthly    = "blue"
          annual     = "green"
          "one-time" = "lightGray"
        }
      }
      "source" = {
        title    = "Source"
        required = false
        enum     = ["manual", "opencost", "litellm"]
        enum_colors = {
          manual   = "lightGray"
          opencost = "blue"
          litellm  = "purple"
        }
      }
      "notes" = { title = "Notes", required = false }
    }
  }
  calculation_properties = {
    "monthlyCost" = {
      title       = "Monthly Cost (USD)"
      type        = "number"
      calculation = "if .properties.cadence == \"annual\" then (.properties.amount / 12) elif .properties.cadence == \"monthly\" then .properties.amount else 0 end"
    }
  }
}
