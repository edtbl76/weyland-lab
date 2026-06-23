# __generated__ by OpenTofu
# Please review these resources and move them into your main configuration files.

# __generated__ by OpenTofu from "system"
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

# __generated__ by OpenTofu from "api:ollama-api"
resource "port_entity" "ollama_api" {
  blueprint                       = "api"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "ollama-api"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      definition  = "Ollama /v1 (OpenAI-compatible) + native /api/tags. See docs/runbooks/model-serving-ollama.md."
      description = "Ollama OpenAI-compatible /v1 + native /api. CT 102, ollama.weyland.lab:11434."
      lifecycle   = "production"
      type        = "openapi"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "model-serving"
    }
  }
  run_id = null
  teams  = null
  title  = "ollama-api"
}

# __generated__ by OpenTofu from "component:ollama"
resource "port_entity" "ollama" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "ollama"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["ollama", "llm", "cpu"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "CPU LLM serving (CT 102) — 6 GGUF models, OpenAI /v1, one model resident. ollama.weyland.lab:11434."
      lifecycle   = "production"
      source      = null
      type        = "service"
    }
  }
  relations = {
    many_relations = {
      consumesApis = []
      dependsOn    = []
      k8sWorkload  = []
      providesApis = ["ollama-api"]
    }
    single_relations = {
      system = "model-serving"
    }
  }
  run_id = null
  teams  = null
  title  = "ollama"
}

# __generated__ by OpenTofu from "component:whisper-stt"
resource "port_entity" "whisper_stt" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "whisper-stt"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["whisper", "stt", "cpu"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "CPU speech-to-text (CT 103) — whisper.cpp native /inference + OpenAI-compatible shim. whisper.weyland.lab."
      lifecycle   = "production"
      source      = null
      type        = "service"
    }
  }
  relations = {
    many_relations = {
      consumesApis = []
      dependsOn    = []
      k8sWorkload  = []
      providesApis = ["whisper-stt-api"]
    }
    single_relations = {
      system = "model-serving"
    }
  }
  run_id = null
  teams  = null
  title  = "whisper-stt"
}

# __generated__ by OpenTofu from "system:rag-platform"
resource "port_entity" "rag_platform" {
  blueprint                       = "system"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "rag-platform"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Retrieval, ingestion, eval, and the 4 vector/graph datastores. The platform's data plane."
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      domain = "weyland"
    }
  }
  run_id = null
  teams  = null
  title  = "rag-platform"
}

# __generated__ by OpenTofu from "system:agents"
resource "port_entity" "agents" {
  blueprint                       = "system"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "agents"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Autonomous agents and their front doors (Hermes)."
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      domain = "weyland"
    }
  }
  run_id = null
  teams  = null
  title  = "agents"
}

# __generated__ by OpenTofu from "api:weyland-mcp"
resource "port_entity" "weyland_mcp" {
  blueprint                       = "api"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "weyland-mcp"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      definition  = "MCP (Streamable HTTP) read-only tool surface. See docs/api.md and docs/diagrams/flow-agent-mcp.md."
      description = "System-view MCP server (read-only tools — status, context_search, context_ask, list_models). Streamable HTTP at /mcp."
      lifecycle   = "production"
      type        = "mcp"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "weyland-mcp"
}

# __generated__ by OpenTofu from "component:open-webui"
resource "port_entity" "open_webui" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "open-webui"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["ui", "chat"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Browser voice/chat front door — chat to Ollama, STT via the whisper shim. chat.weyland.lab."
      lifecycle   = "production"
      source      = null
      type        = "website"
    }
  }
  relations = {
    many_relations = {
      consumesApis = ["ollama-api", "whisper-stt-api"]
      dependsOn    = []
      k8sWorkload  = ["open-webui-Deployment-weyland-weyland-cluster"]
      providesApis = []
    }
    single_relations = {
      system = "model-serving"
    }
  }
  run_id = null
  teams  = null
  title  = "open-webui"
}

# __generated__ by OpenTofu from "api:whisper-stt-api"
resource "port_entity" "whisper_stt_api" {
  blueprint                       = "api"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "whisper-stt-api"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      definition  = "/v1/audio/transcriptions (OpenAI shim) + native /inference. See docs/runbooks/transcription-whisper.md."
      description = "OpenAI-compatible STT shim + native whisper.cpp /inference. CT 103."
      lifecycle   = "production"
      type        = "openapi"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "model-serving"
    }
  }
  run_id = null
  teams  = null
  title  = "whisper-stt-api"
}

# __generated__ by OpenTofu from "component:hermes"
resource "port_entity" "hermes" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "hermes"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["agent", "mcp", "telegram"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Primary autonomous agent (CT 104). qwen3-coder brain via Ollama, MCP client of the tool-server, Telegram front door, native SQLite Kanban (B27)."
      lifecycle   = "production"
      source      = null
      type        = "service"
    }
  }
  relations = {
    many_relations = {
      consumesApis = ["weyland-mcp", "ollama-api", "litellm-openai"]
      dependsOn    = []
      k8sWorkload  = []
      providesApis = []
    }
    single_relations = {
      system = "agents"
    }
  }
  run_id = null
  teams  = null
  title  = "hermes"
}

# __generated__ by OpenTofu from "domain:weyland"
resource "port_entity" "weyland" {
  blueprint                       = "domain"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "weyland"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "The weyland homelab — a single-node AI platform (Minisforum MS-A2, Proxmox + k3s)."
    }
  }
  relations = null
  run_id    = null
  teams     = null
  title     = "weyland"
}

# __generated__ by OpenTofu from "domain"
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

# __generated__ by OpenTofu from "component:weyland-docs"
resource "port_entity" "weyland_docs" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "weyland-docs"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["docs", "techdocs"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Platform documentation (runbooks, architecture, diagrams, concepts) — rendered as TechDocs (docs/ tree)."
      lifecycle   = "production"
      source      = "https://github.com/edtbl76/weyland-lab/tree/main/docs"
      type        = "documentation"
    }
  }
  relations = {
    many_relations = {
      consumesApis = []
      dependsOn    = []
      k8sWorkload  = []
      providesApis = []
    }
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "weyland-docs"
}

# __generated__ by OpenTofu from "resource:weaviate"
resource "port_entity" "weaviate" {
  blueprint                       = "resource"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "weaviate"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["weaviate", "vector"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Vector store — class WeylandChunk. mother:30087."
      type        = "database"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "weaviate"
}

# __generated__ by OpenTofu from "component:weyland-tool-server"
resource "port_entity" "weyland_tool_server" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "weyland-tool-server"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["python", "fastapi", "rag", "mcp"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "FastAPI platform boundary — RAG retrieval (4 backends), /context/ask, /evals/*, /pipeline/trigger, /mcp + /mcp-act, B14 guardrails. mother:30080."
      lifecycle   = "production"
      source      = "https://github.com/edtbl76/weyland-lab/tree/main/nodes/mother/lab/weyland-platform/services/weyland-tool-server/"
      type        = "service"
    }
  }
  relations = {
    many_relations = {
      consumesApis = ["litellm-openai", "ollama-api"]
      dependsOn    = ["postgres-pgvector", "qdrant", "weaviate", "neo4j"]
      k8sWorkload  = ["weyland-tool-server-Deployment-weyland-weyland-cluster"]
      providesApis = ["weyland-mcp", "weyland-rest"]
    }
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "weyland-tool-server"
}

# __generated__ by OpenTofu from "resource:qdrant"
resource "port_entity" "qdrant" {
  blueprint                       = "resource"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "qdrant"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["qdrant", "vector"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Vector store — collection weyland_chunks. mother:30083/30084."
      type        = "database"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "qdrant"
}

# __generated__ by OpenTofu from "component:neodash"
resource "port_entity" "neodash" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "neodash"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["ui", "neo4j", "viz"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Neo4j dashboard/viz UI (free Bloom-alternative). mother:30088."
      lifecycle   = "production"
      source      = null
      type        = "website"
    }
  }
  relations = {
    many_relations = {
      consumesApis = []
      dependsOn    = ["neo4j"]
      k8sWorkload  = ["neodash-Deployment-weyland-weyland-cluster"]
      providesApis = []
    }
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "neodash"
}

# __generated__ by OpenTofu from "resource"
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

# __generated__ by OpenTofu from "component:litellm-gateway"
resource "port_entity" "litellm_gateway" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "litellm-gateway"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["litellm", "gateway", "llm"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "OpenAI-compatible hosted-model gateway fronting Gemini + OpenRouter (free tiers); off-LAN egress valve + spend alerts. mother:30400."
      lifecycle   = "production"
      source      = null
      type        = "service"
    }
  }
  relations = {
    many_relations = {
      consumesApis = []
      dependsOn    = []
      k8sWorkload  = ["litellm-Deployment-weyland-weyland-cluster"]
      providesApis = ["litellm-openai"]
    }
    single_relations = {
      system = "model-serving"
    }
  }
  run_id = null
  teams  = null
  title  = "litellm-gateway"
}

# __generated__ by OpenTofu from "api"
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

# __generated__ by OpenTofu from "component:n8n"
resource "port_entity" "n8n" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "n8n"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["ui", "automation"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Workflow automation (ingestion role retired -> Dagster; retained for other automation). n8n.weyland.lab."
      lifecycle   = "production"
      source      = null
      type        = "service"
    }
  }
  relations = {
    many_relations = {
      consumesApis = []
      dependsOn    = []
      k8sWorkload  = ["n8n-Deployment-n8n-weyland-cluster"]
      providesApis = []
    }
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "n8n"
}

# __generated__ by OpenTofu from "resource:minio"
resource "port_entity" "minio" {
  blueprint                       = "resource"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "minio"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["minio", "s3", "storage"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "S3-compatible object storage (8 TB USB -> mother). Hosts the aidlc-kb bucket + tofu-state. s3.weyland.lab."
      type        = "object-store"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "minio"
}

# __generated__ by OpenTofu from "component"
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

# __generated__ by OpenTofu from "resource:neo4j"
resource "port_entity" "neo4j" {
  blueprint                       = "resource"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "neo4j"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["neo4j", "graph", "gds"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Graph + vector index (APOC + GDS). GraphRAG Document/Chunk + the B37 AIDLC :Entry graph. mother:30085/30086."
      type        = "database"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "neo4j"
}

# __generated__ by OpenTofu from "resource:aidlc-kb-corpus"
resource "port_entity" "aidlc_kb_corpus" {
  blueprint                       = "resource"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "aidlc-kb-corpus"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["corpus", "rag", "aidlc"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "B37 AIDLC knowledge corpus (~510 brand-neutral entries) in MinIO bucket aidlc-kb, ingested to all 4 backends + Neo4j :Entry graph."
      type        = "dataset"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "aidlc-kb-corpus"
}

# __generated__ by OpenTofu from "api:litellm-openai"
resource "port_entity" "litellm_openai" {
  blueprint                       = "api"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "litellm-openai"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      definition  = "OpenAI-compatible /v1 (chat/completions, models). See docs/runbooks/model-gateway.md."
      description = "OpenAI-compatible /v1 gateway (Gemini + OpenRouter). mother:30400."
      lifecycle   = "production"
      type        = "openapi"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "model-serving"
    }
  }
  run_id = null
  teams  = null
  title  = "litellm-openai"
}

# __generated__ by OpenTofu from "api:weyland-rest"
resource "port_entity" "weyland_rest" {
  blueprint                       = "api"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "weyland-rest"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      definition  = "REST surface of weyland-tool-server. Full endpoint list in docs/api.md."
      description = "Tool-server REST — /context/search, /context/ask, /evals/*, /pipeline/trigger, /metrics, health."
      lifecycle   = "production"
      type        = "rest"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "weyland-rest"
}

# __generated__ by OpenTofu from "resource:postgres-pgvector"
resource "port_entity" "postgres_pgvector" {
  blueprint                       = "resource"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "postgres-pgvector"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["postgres", "pgvector", "database"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Primary RAG store — rag_documents/rag_chunks (384-dim bge) + eval_* + model_catalog. In-cluster :5432."
      type        = "database"
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "postgres-pgvector"
}

# __generated__ by OpenTofu from "component:dagster"
resource "port_entity" "dagster" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "dagster"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["python", "dagster", "etl"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "Pipeline orchestration — git-pull ingestion (docs/+nodes/), eval jobs, model_catalog (6h), AIDLC-KB ingest. dagster.weyland.lab."
      lifecycle   = "production"
      source      = null
      type        = "service"
    }
  }
  relations = {
    many_relations = {
      consumesApis = []
      dependsOn    = ["postgres-pgvector", "qdrant", "weaviate", "neo4j", "minio", "aidlc-kb-corpus"]
      k8sWorkload  = ["dagster-daemon-Deployment-weyland-weyland-cluster", "dagster-user-code-Deployment-weyland-weyland-cluster", "dagster-webserver-Deployment-weyland-weyland-cluster"]
      providesApis = []
    }
    single_relations = {
      system = "rag-platform"
    }
  }
  run_id = null
  teams  = null
  title  = "dagster"
}

# __generated__ by OpenTofu from "system:model-serving"
resource "port_entity" "model_serving" {
  blueprint                       = "system"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "model-serving"
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "LLM + STT inference and the hosted-model gateway."
    }
  }
  relations = {
    many_relations = null
    single_relations = {
      domain = "weyland"
    }
  }
  run_id = null
  teams  = null
  title  = "model-serving"
}

# __generated__ by OpenTofu from "component:mlflow"
resource "port_entity" "mlflow" {
  blueprint                       = "component"
  create_missing_related_entities = null
  icon                            = null
  identifier                      = "mlflow"
  properties = {
    array_props = {
      boolean_items = null
      number_items  = null
      object_items  = null
      string_items = {
        tags = ["mlflow", "tracking"]
      }
    }
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      description = "MLflow — experiment tracking + model registry (Postgres backend, MinIO artifacts). B10+B16. mlflow.weyland.lab."
      lifecycle   = "production"
      source      = null
      type        = "service"
    }
  }
  relations = {
    many_relations = {
      consumesApis = []
      dependsOn    = ["postgres-pgvector", "minio"]
      k8sWorkload  = ["mlflow-Deployment-weyland-weyland-cluster"]
      providesApis = []
    }
    single_relations = {
      system = "model-serving"
    }
  }
  run_id = null
  teams  = null
  title  = "mlflow"
}
