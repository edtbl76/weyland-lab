# B129 — machine-inventory catalog blueprints: host + installed_package.
#
# Blueprints are tofu (this file); ENTITIES are emitted from machine-inventory.yaml by
# scripts/machine_inventory.py emit via the Port REST API (NOT `port_entity` here — per applications.tf,
# B137 moved entity emission out of tofu). Apply with `tofu apply` in this dir (creds in ./.env); confirm
# with `tofu validate` first. See docs/runbooks/machine-inventory.md.

resource "port_blueprint" "host" {
  calculation_properties      = null
  create_catalog_page         = true
  description                 = "A lab machine tracked in the machine-inventory catalog (B129)."
  force_delete_entities       = false
  icon                        = "Server"
  identifier                  = "host"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  title                       = "Host"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      role = {
        date_format         = null
        default             = null
        description         = "what the machine is for"
        enum                = null
        enum_colors         = null
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Role"
      }
    }
  }
  relations = null
}

resource "port_blueprint" "installed_package" {
  calculation_properties      = null
  create_catalog_page         = true
  description                 = "A package/app/image installed on a host, with its keep/remove disposition (B129)."
  force_delete_entities       = false
  icon                        = "Package"
  identifier                  = "installed_package"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  title                       = "Installed Package"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      kind = {
        date_format         = null
        default             = null
        description         = "package manager / source"
        enum                = ["snap", "flatpak", "apt", "pip", "npm", "image"]
        enum_colors         = null
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Kind"
      }
      package = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Package"
      }
      version = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Version"
      }
      status = {
        date_format = null
        default     = null
        description = "keep/remove disposition; system = dep baseline; unreviewed = new, needs a decision"
        enum        = ["keep", "remove", "system", "unreviewed"]
        enum_colors = {
          keep       = "green"
          remove     = "red"
          system     = "lightGray"
          unreviewed = "orange"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Status"
      }
      rationale = {
        date_format         = null
        default             = null
        description         = "one line: why it is here / why keep or remove"
        enum                = null
        enum_colors         = null
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Rationale"
      }
    }
  }
  relations = {
    host = {
      description = null
      many        = false
      required    = false
      target      = "host"
      title       = "Host"
    }
  }
}
