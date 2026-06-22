# Port `cost` blueprint (B55) — codified. Imported from the live Port resource via `tofu plan -generate-config-out`
# then cleaned (dropped computed fields: id, created_at/by, updated_at/by). `tofu plan` should be a no-op.
resource "port_blueprint" "cost" {
  identifier            = "cost"
  title                 = "Recurring Cost"
  icon                  = "Cost"
  create_catalog_page   = true
  force_delete_entities = false

  properties = {
    number_props = {
      "amount" = {
        title    = "Amount (USD)"
        required = false
      }
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
      "vendor" = {
        title    = "Vendor"
        required = false
      }
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
      "notes" = {
        title    = "Notes"
        required = false
      }
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
