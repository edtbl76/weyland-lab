resource "port_blueprint" "system" {
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Cluster"
  identifier                  = "system"
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
    }
  }
  relations = {
    domain = {
      description = null
      many        = false
      required    = false
      target      = "domain"
      title       = "Domain"
    }
  }
  title                         = "System"
  webhook_changelog_destination = null
}

resource "port_blueprint" "domain" {
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "BlankPage"
  identifier                  = "domain"
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
    }
  }
  relations                     = null
  title                         = "Domain"
  webhook_changelog_destination = null
}

resource "port_blueprint" "resource" {
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Database"
  identifier                  = "resource"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  properties = {
    array_props = {
      tags = {
        boolean_items = null
        description   = null
        icon          = null
        max_items     = null
        min_items     = null
        number_items  = null
        object_items  = null
        required      = false
        string_items  = null
        title         = "Tags"
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
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
      type = {
        date_format = null
        default     = null
        description = null
        enum        = ["database", "object-store", "dataset"]
        enum_colors = {
          database     = "blue"
          dataset      = "green"
          object-store = "yellow"
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
    }
  }
  relations = {
    system = {
      description = null
      many        = false
      required    = false
      target      = "system"
      title       = "System"
    }
  }
  title                         = "Resource"
  webhook_changelog_destination = null
}

resource "port_blueprint" "api" {
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Api"
  identifier                  = "api"
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
      definition = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "markdown"
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Definition"
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
      lifecycle = {
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
        title               = "Lifecycle"
      }
      type = {
        date_format = null
        default     = null
        description = null
        enum        = ["openapi", "mcp", "rest", "grpc"]
        enum_colors = {
          grpc    = "orange"
          mcp     = "purple"
          openapi = "green"
          rest    = "blue"
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
    }
  }
  relations = {
    system = {
      description = null
      many        = false
      required    = false
      target      = "system"
      title       = "System"
    }
  }
  title                         = "API"
  webhook_changelog_destination = null
}

resource "port_blueprint" "component" {
  calculation_properties      = null
  create_catalog_page         = true
  description                 = null
  force_delete_entities       = false
  icon                        = "Microservice"
  identifier                  = "component"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership = {
    type  = "Direct"
    title = "Owning Teams"
  }
  properties = {
    array_props = {
      tags = {
        boolean_items = null
        description   = null
        icon          = null
        max_items     = null
        min_items     = null
        number_items  = null
        object_items  = null
        required      = false
        string_items  = null
        title         = "Tags"
      }
      capabilities = {
        boolean_items = null
        description   = "What this app does — from the B82 registry (applications.yaml)."
        icon          = null
        max_items     = null
        min_items     = null
        number_items  = null
        object_items  = null
        required      = false
        string_items  = null
        title         = "Capabilities"
      }
    }
    boolean_props = {
      is_data_application = {
        default     = null
        description = "Owns cataloged data (has a DataHub Application entity) vs pure compute. B82 taxonomy."
        icon        = null
        required    = false
        title       = "Data Application"
      }
    }
    number_props  = null
    object_props  = null
    string_props = {
      datahub_application_url = {
        date_format         = null
        default             = null
        description         = "Link to this app's DataHub Application page (data-apps only). B82."
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
        title               = "DataHub Application"
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
      lifecycle = {
        date_format = null
        default     = null
        description = null
        enum        = ["production", "experimental", "deprecated"]
        enum_colors = {
          deprecated   = "red"
          experimental = "orange"
          production   = "green"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Lifecycle"
      }
      source = {
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
        title               = "Source"
      }
      type = {
        date_format = null
        default     = null
        description = null
        enum        = ["service", "website", "documentation"]
        enum_colors = {
          documentation = "lightGray"
          service       = "blue"
          website       = "turquoise"
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
    }
  }
  relations = {
    consumesApis = {
      description = null
      many        = true
      required    = false
      target      = "api"
      title       = "Consumes APIs"
    }
    dependsOn = {
      description = null
      many        = true
      required    = false
      target      = "resource"
      title       = "Depends On"
    }
    k8sWorkload = {
      description = null
      many        = true
      required    = false
      target      = "k8s_workload"
      title       = "K8s Workload"
    }
    providesApis = {
      description = null
      many        = true
      required    = false
      target      = "api"
      title       = "Provides APIs"
    }
    service = {
      description = null
      many        = false
      required    = false
      target      = "service"
      title       = "Repo / Service (DORA)"
    }
    system = {
      description = null
      many        = false
      required    = false
      target      = "system"
      title       = "System"
    }
  }
  title                         = "Component"
  webhook_changelog_destination = null
}

