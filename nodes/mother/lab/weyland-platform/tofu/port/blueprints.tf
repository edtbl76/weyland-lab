# __generated__ by OpenTofu
# Please review these resources and move them into your main configuration files.

# __generated__ by OpenTofu from "security_scan"
resource "port_blueprint" "security_scan" {
  provider                    = port-labs
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Lock"
  identifier                  = "security_scan"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  properties = {
    array_props   = null
    boolean_props = null
    number_props = {
      critical = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Critical"
      }
      high = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "High"
      }
      low = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Low"
      }
      medium = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Medium"
      }
      total = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Total Findings"
      }
    }
    object_props = null
    string_props = {
      scannedAt = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "date-time"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Scanned At"
      }
      target = {
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
        title               = "Target Repo"
      }
      tool = {
        date_format = null
        default     = null
        description = null
        enum        = ["trivy", "semgrep"]
        enum_colors = {
          semgrep = "purple"
          trivy   = "blue"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Scanner"
      }
    }
  }
  relations                     = null
  title                         = "Security Scan"
  webhook_changelog_destination = null
}

# __generated__ by OpenTofu from "glitchtip_issue"
resource "port_blueprint" "glitchtip_issue" {
  provider                    = port-labs
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Bug"
  identifier                  = "glitchtip_issue"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  properties = {
    array_props   = null
    boolean_props = null
    number_props = {
      count = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Event Count"
      }
    }
    object_props = null
    string_props = {
      culprit = {
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
        title               = "Culprit"
      }
      environment = {
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
        title               = "Environment"
      }
      lastSeen = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "date-time"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Last Seen"
      }
      level = {
        date_format = null
        default     = null
        description = null
        enum        = ["fatal", "error", "warning", "info", "debug"]
        enum_colors = {
          debug   = "lightGray"
          error   = "red"
          fatal   = "red"
          info    = "blue"
          warning = "orange"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Level"
      }
      project = {
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
        title               = "Project / App"
      }
      serverName = {
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
        title               = "Server / Pod"
      }
      status = {
        date_format = null
        default     = null
        description = null
        enum        = ["unresolved", "resolved", "muted"]
        enum_colors = {
          muted      = "lightGray"
          resolved   = "green"
          unresolved = "red"
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
      url = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "url"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "GlitchTip Link"
      }
    }
  }
  relations                     = null
  title                         = "Error Issue"
  webhook_changelog_destination = null
}

# __generated__ by OpenTofu from "feature_flag"
resource "port_blueprint" "feature_flag" {
  provider                    = port-labs
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Flag"
  identifier                  = "feature_flag"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  properties = {
    array_props = null
    boolean_props = {
      enabled = {
        default     = null
        description = "Whether the flag is on in the environment"
        icon        = null
        required    = false
        title       = "Enabled"
      }
      stale = {
        default     = null
        description = "Flagged as stale in Unleash"
        icon        = null
        required    = false
        title       = "Stale"
      }
    }
    number_props = null
    object_props = null
    string_props = {
      createdAt = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "date-time"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Created At"
      }
      description = {
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
        title               = "Description"
      }
      environment = {
        date_format         = null
        default             = null
        description         = "Unleash environment (development/production)"
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
        title               = "Environment"
      }
      flagType = {
        date_format = null
        default     = null
        description = "Unleash flag type"
        enum        = ["release", "experiment", "operational", "kill-switch", "permission"]
        enum_colors = {
          experiment  = "blue"
          kill-switch = "red"
          operational = "purple"
          permission  = "orange"
          release     = "green"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Type"
      }
      project = {
        date_format         = null
        default             = null
        description         = "Unleash project the flag belongs to"
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
        title               = "Project"
      }
      url = {
        date_format         = null
        default             = null
        description         = "Deep link to the flag in Unleash"
        enum                = null
        enum_colors         = null
        format              = "url"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Unleash URL"
      }
    }
  }
  relations                     = null
  title                         = "Feature Flag"
  webhook_changelog_destination = null
}

# __generated__ by OpenTofu from "code_quality"
resource "port_blueprint" "code_quality" {
  provider                    = port-labs
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Sonarqube"
  identifier                  = "code_quality"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      analyzedAt = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "date-time"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Analyzed At"
      }
      branch = {
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
        title               = "Branch"
      }
      project = {
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
        title               = "Project"
      }
      qualityGate = {
        date_format = null
        default     = null
        description = null
        enum        = ["OK", "ERROR", "WARN", "NONE"]
        enum_colors = {
          ERROR = "red"
          NONE  = "lightGray"
          OK    = "green"
          WARN  = "orange"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Quality Gate"
      }
      url = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "url"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "SonarQube Dashboard"
      }
    }
  }
  relations                     = null
  title                         = "Code Quality"
  webhook_changelog_destination = null
}

# __generated__ by OpenTofu from "endpoint"
resource "port_blueprint" "endpoint" {
  provider                    = port-labs
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Link"
  identifier                  = "endpoint"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      access = {
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
        title               = "Access"
      }
      category = {
        date_format = null
        default     = null
        description = null
        enum        = ["UI", "Model API", "Platform API", "Data", "Gateway", "Storage", "SaaS", "Infra"]
        enum_colors = {
          Data           = "green"
          Gateway        = "orange"
          Infra          = "lightGray"
          "Model API"    = "purple"
          "Platform API" = "turquoise"
          SaaS           = "pink"
          Storage        = "yellow"
          UI             = "blue"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Category"
      }
      description = {
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
        title               = "Description"
      }
      host = {
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
        title               = "Host"
      }
      url = {
        date_format         = null
        default             = null
        description         = "Click to launch"
        enum                = null
        enum_colors         = null
        format              = "url"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Open"
      }
    }
  }
  relations                     = null
  title                         = "Endpoint"
  webhook_changelog_destination = null
}

# __generated__ by OpenTofu from "ci_pipeline"
resource "port_blueprint" "ci_pipeline" {
  provider                    = port-labs
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Deployment"
  identifier                  = "ci_pipeline"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  properties = {
    array_props   = null
    boolean_props = null
    number_props = {
      pipelineNumber = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Pipeline #"
      }
    }
    object_props = null
    string_props = {
      branch = {
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
        title               = "Branch"
      }
      commit = {
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
        title               = "Commit"
      }
      event = {
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
        title               = "Trigger"
      }
      finishedAt = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "date-time"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Finished"
      }
      repo = {
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
        title               = "Repository"
      }
      status = {
        date_format = null
        default     = null
        description = null
        enum        = ["success", "failure", "running", "pending", "error", "killed", "skipped"]
        enum_colors = {
          error   = "red"
          failure = "red"
          killed  = "orange"
          pending = "lightGray"
          running = "blue"
          skipped = "lightGray"
          success = "green"
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
      url = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "url"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Woodpecker Link"
      }
    }
  }
  relations                     = null
  title                         = "CI Pipeline"
  webhook_changelog_destination = null
}
