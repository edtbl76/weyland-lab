resource "port_blueprint" "environment" {
  identifier                    = "environment"
  title                         = "Environment"
  icon                          = "Environment"
  description                   = null
  calculation_properties        = null
  mirror_properties             = null
  create_catalog_page           = true
  force_delete_entities         = false
  include_in_global_search      = null
  kafka_changelog_destination   = null
  ownership                     = null
  webhook_changelog_destination = null
  properties                    = null
  relations = {
    k8s_cluster = {
      description = null
      many        = false
      required    = false
      target      = "k8s_cluster"
      title       = "Cluster"
    }
  }
}
resource "port_blueprint" "ai_session" {
  identifier                    = "ai_session"
  title                         = "AI Session"
  icon                          = "Robot"
  description                   = null
  create_catalog_page           = true
  force_delete_entities         = false
  include_in_global_search      = null
  kafka_changelog_destination   = null
  webhook_changelog_destination = null
  ownership                     = null
  properties = {
    array_props = {
      models = {
        boolean_items = null
        description   = null
        icon          = null
        max_items     = null
        min_items     = null
        number_items  = null
        object_items  = null
        required      = false
        string_items  = null
        title         = "Models"
      }
    }
    boolean_props = null
    number_props = {
      api_equiv_value_usd = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "API-Equivalent Value (USD)"
      }
      assistant_turns = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Assistant Turns"
      }
      cache_creation_tokens = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Cache Creation Tokens"
      }
      cache_read_tokens = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Cache Read Tokens"
      }
      duration_minutes = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Duration (min)"
      }
      estimated_cost_usd = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Est. Cost (USD)"
      }
      input_tokens = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Input Tokens"
      }
      output_tokens = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Output Tokens (generation)"
      }
      tools_invoked = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Tools Invoked"
      }
      total_tokens = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Total Tokens (in+out)"
      }
      user_turns = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "User Turns"
      }
    }
    object_props = null
    string_props = {
      ended_at = {
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
        title               = "Ended"
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
      started_at = {
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
        title               = "Started"
      }
    }
  }
  relations = {
    service = {
      description = null
      many        = false
      required    = false
      target      = "service"
      title       = "Service"
    }
  }
  mirror_properties      = null
  calculation_properties = null
}

resource "port_blueprint" "ai_user" {
  identifier                    = "ai_user"
  title                         = "AI User Profile"
  icon                          = "User"
  description                   = null
  create_catalog_page           = true
  force_delete_entities         = false
  include_in_global_search      = null
  kafka_changelog_destination   = null
  webhook_changelog_destination = null
  ownership                     = null
  properties = {
    array_props   = null
    boolean_props = null
    number_props = {
      code_acceptances_monthly = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Code Acceptances (Monthly)"
      }
      code_generations_monthly = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Code Generations (Monthly)"
      }
      days_active_monthly = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Days Active (Monthly)"
      }
      loc_added_monthly = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "LOC Added (Monthly)"
      }
      loc_suggested_monthly = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "LOC Suggested (Monthly)"
      }
    }
    object_props = null
    string_props = {
      display_name = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = null
        icon                = "User"
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Display Name"
      }
      email = {
        date_format         = null
        default             = null
        description         = null
        enum                = null
        enum_colors         = null
        format              = "user"
        icon                = "User"
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Email"
      }
      tool = {
        date_format = null
        default     = null
        description = null
        enum        = ["Claude", "Copilot", "Cursor", "Custom"]
        enum_colors = {
          "Claude"  = "purple"
          "Copilot" = "blue"
          "Cursor"  = "green"
          "Custom"  = "lightGray"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "AI Tool"
      }
    }
  }
  relations              = null
  mirror_properties      = null
  calculation_properties = null
}

resource "port_blueprint" "backup" {
  identifier                    = "backup"
  title                         = "Backup"
  icon                          = "Cluster"
  description                   = null
  create_catalog_page           = true
  force_delete_entities         = false
  include_in_global_search      = null
  kafka_changelog_destination   = null
  webhook_changelog_destination = null
  ownership                     = null
  properties = {
    array_props   = null
    boolean_props = null
    number_props = {
      dataAddedBytes = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Data added (bytes)"
      }
      durationSeconds = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Duration (s)"
      }
      filesChanged = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Files changed"
      }
      filesNew = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Files new"
      }
      repoSizeBytes = {
        default     = null
        description = null
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Repo size (bytes)"
      }
    }
    object_props = null
    string_props = {
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
        title               = "Finished at"
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
        required            = true
        spec                = null
        spec_authentication = null
        title               = "Host"
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
      snapshotId = {
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
        title               = "Snapshot ID"
      }
      status = {
        date_format = null
        default     = null
        description = null
        enum        = ["success", "failure"]
        enum_colors = {
          "failure" = "red"
          "success" = "green"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = true
        spec                = null
        spec_authentication = null
        title               = "Status"
      }
    }
  }
  relations         = null
  mirror_properties = null
  calculation_properties = {
    repoSize = {
      calculation         = "(.properties.repoSizeBytes / 1048576) | floor | tostring + \" MiB\""
      colorized           = null
      colors              = null
      date_format         = null
      description         = null
      format              = null
      icon                = null
      spec                = null
      spec_authentication = null
      title               = "Repo size"
      type                = "string"
    }
  }
}

# EMA-172 (2026-08-27) — `lead_time_hours` + `pull_request_url` added, and they are deliberately
# PROPERTIES rather than a relation-mirror.
#
# `github_lead_time_hours` below mirrors `github_pull_request.cycle_time_hours`, which is structurally
# ALWAYS NULL here: the github-weyland Ocean integration fetches only OPEN PRs, and cycle_time_hours
# is computed on MERGE. So a PR has no cycle time while it is visible and stops being visible the
# moment it would have one. Measured 2026-08-27: 10 PR entities, all `open`, zero with a cycle time.
#
# B144's reaper then makes it permanent — it deletes closed PR entities nightly, so a deployment's
# `github_pull_request` relation would dangle the night after every ship.
#
# `ship-images.sh` already knows both timestamps at merge time, so it writes the real number here and
# links the PR as a plain URL that cannot dangle. The mirrors are kept, unused, rather than removed:
# they cost nothing and they document why this property exists.
resource "port_blueprint" "deployment" {
  identifier                    = "deployment"
  title                         = "Deployment"
  icon                          = "Deployment"
  description                   = "A production deployment created from a merged PR to the default branch"
  create_catalog_page           = true
  force_delete_entities         = false
  include_in_global_search      = null
  kafka_changelog_destination   = null
  webhook_changelog_destination = null
  ownership                     = null
  properties = {
    array_props   = null
    boolean_props = null
    number_props = {
      lead_time_hours = {
        default     = null
        description = "Hours from first commit on the PR branch to the deploy landing. Written directly by ship-images.sh at emit time - NOT mirrored from the PR, whose cycle_time_hours is structurally always null here."
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        spec        = null
        title       = "Lead Time for Changes (Hours)"
        unit        = null
      }
    }
    object_props  = null
    string_props = {
      pull_request_url = {
        date_format         = null
        default             = null
        description         = "Plain link, not a relation - B144's reaper deletes closed PR entities nightly, so a relation here would dangle after every ship."
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
        title               = "Pull Request"
      }
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
        title               = "Deployment Time"
      }
      deploymentStatus = {
        date_format = null
        default     = null
        description = null
        enum        = ["Success", "Failure", "Pending"]
        enum_colors = {
          "Failure" = "red"
          "Pending" = "yellow"
          "Success" = "green"
        }
        format              = null
        icon                = null
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Deployment Status"
      }
      environment = {
        date_format = null
        default     = null
        description = null
        enum        = ["Production", "Staging", "Development"]
        enum_colors = {
          "Development" = "blue"
          "Production"  = "green"
          "Staging"     = "yellow"
        }
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
    }
  }
  relations = {
    github_pull_request = {
      description = null
      many        = false
      required    = false
      target      = "githubPullRequest"
      title       = "Pull Request"
    }
    service = {
      description = null
      many        = false
      required    = false
      target      = "service"
      title       = "Service"
    }
  }
  mirror_properties = {
    github_lead_time_hours = {
      path  = "github_pull_request.cycle_time_hours"
      title = "Lead Time for Changes (Hours)"
    }
    github_repo_id = {
      path  = "github_pull_request.repository.$identifier"
      title = "GitHub Repository ID"
    }
  }
  calculation_properties = null
}

resource "port_blueprint" "organization" {
  identifier                    = "organization"
  title                         = "Organization"
  icon                          = "Organization"
  description                   = "A logical organization grouping teams and services"
  create_catalog_page           = true
  force_delete_entities         = false
  include_in_global_search      = null
  kafka_changelog_destination   = null
  webhook_changelog_destination = null
  ownership                     = null
  properties                    = null
  relations                     = null
  mirror_properties             = null
  calculation_properties = {
    ai_acceptance_rate = {
      calculation         = "if (.properties.ai_code_generations_monthly // 0) > 0 then ((.properties.ai_code_acceptances_monthly // 0) / .properties.ai_code_generations_monthly) * 100 | round else 0 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Org-level AI suggestion acceptance rate this month"
      format              = null
      icon                = null
      spec                = null
      spec_authentication = null
      title               = "AI Acceptance Rate (%)"
      type                = "number"
    }
    ai_adoption_rate = {
      calculation         = "(.properties.total_port_users // 0) as $t | if $t == 0 then 0 else ((.properties.ai_active_users_monthly // 0) / $t) * 100 | round end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of all Port users actively using any AI tool this month"
      format              = null
      icon                = null
      spec                = null
      spec_authentication = null
      title               = "AI Adoption Rate (%)"
      type                = "number"
    }
    ai_high_adopter_rate = {
      calculation         = "(.properties.total_port_users // 0) as $t | if $t == 0 then 0 else ((.properties.ai_high_adopters_monthly // 0) / $t) * 100 | round end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of Port users who reached High tier (16+ days active) this month"
      format              = null
      icon                = null
      spec                = null
      spec_authentication = null
      title               = "AI High Adoption Rate (%)"
      type                = "number"
    }
    ai_inactive_license_rate = {
      calculation         = "((.properties.ai_active_users_monthly // 0) + (.properties.ai_inactive_users_monthly // 0)) as $total | if $total == 0 then 0 else ((.properties.ai_inactive_users_monthly // 0) / $total) * 100 | round end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of users with an AI profile but zero activity this month"
      format              = null
      icon                = null
      spec                = null
      spec_authentication = null
      title               = "AI Inactive Users (%)"
      type                = "number"
    }
    failure_rate_trend = {
      calculation = "((if (.properties.github_workflow_runs_30d != null and .properties.github_workflow_runs_30d != 0) then ((.properties.github_failed_workflow_runs_30d // 0) / .properties.github_workflow_runs_30d) * 100 | floor else 0 end) - (if (.properties.github_workflow_runs_7d != null and .properties.github_workflow_runs_7d != 0) then ((.properties.github_failed_workflow_runs_7d // 0) / .properties.github_workflow_runs_7d) * 100 | floor else 0 end)) as $diff | if $diff > 0 then \"Improving\" elif $diff < 0 then \"Degrading\" else \"Stable\" end"
      colorized   = true
      colors = {
        "Degrading" = "red"
        "Improving" = "green"
        "Stable"    = "blue"
      }
      date_format         = null
      description         = "Weekly failure rate vs monthly average \u2014 Improving, Stable, or Degrading"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Workflow Failure Rate Trend"
      type                = "string"
    }
    github_cycle_time_trend = {
      calculation = "((.properties.github_pr_cycle_time // 0) - (.properties.github_pr_cycle_time_weekly // 0)) as $diff | if $diff > 0 then \"Improving\" elif $diff < 0 then \"Degrading\" else \"Stable\" end"
      colorized   = true
      colors = {
        "Degrading" = "red"
        "Improving" = "green"
        "Stable"    = "blue"
      }
      date_format         = null
      description         = "Weekly vs monthly PR cycle time \u2014 Improving, Stable, or Degrading"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "PR Cycle Time Trend"
      type                = "string"
    }
    github_merged_prs_per_service_last_month = {
      calculation         = "if (.properties.services_count != null and .properties.services_count != 0) then (.properties.github_merged_prs_last_month / .properties.services_count) else 0 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "PRs merged in the last 30 days divided by number of services in the organization"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Monthly PR Throughput per Service"
      type                = "number"
    }
    github_stale_pr_share_percent = {
      calculation         = "if (.properties.github_open_prs != null and .properties.github_open_prs != 0) then (.properties.github_stale_prs_7d / .properties.github_open_prs) * 100 else 0 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of open PRs that are older than 7 days"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Stale PR Share (%)"
      type                = "number"
    }
    github_throughput_trend = {
      calculation = "((.properties.github_merged_prs_last_week // 0) * 30 - (.properties.github_merged_prs_last_month // 0) * 7) as $diff | if $diff > 0 then \"Improving\" elif $diff < 0 then \"Degrading\" else \"Stable\" end"
      colorized   = true
      colors = {
        "Degrading" = "red"
        "Improving" = "green"
        "Stable"    = "blue"
      }
      date_format         = null
      description         = "Weekly vs monthly PR throughput rate \u2014 Improving, Stable, or Degrading"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "PR Throughput Trend"
      type                = "string"
    }
    monthly_workflow_failure_rate = {
      calculation         = "if (.properties.github_workflow_runs_30d != null and .properties.github_workflow_runs_30d != 0) then ((.properties.github_failed_workflow_runs_30d // 0) / .properties.github_workflow_runs_30d) * 100 | floor else 0 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of workflow runs that failed in the last 30 days"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Monthly Workflow Failure Rate (%)"
      type                = "number"
    }
    weekly_workflow_failure_rate = {
      calculation         = "if (.properties.github_workflow_runs_7d != null and .properties.github_workflow_runs_7d != 0) then ((.properties.github_failed_workflow_runs_7d // 0) / .properties.github_workflow_runs_7d) * 100 | floor else 0 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of workflow runs that failed in the last 7 days"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Weekly Workflow Failure Rate (%)"
      type                = "number"
    }
  }
}

resource "port_blueprint" "service" {
  identifier                    = "service"
  title                         = "Service"
  icon                          = "Microservice"
  description                   = null
  create_catalog_page           = true
  force_delete_entities         = false
  include_in_global_search      = null
  kafka_changelog_destination   = null
  webhook_changelog_destination = null
  ownership = {
    path  = null
    title = null
    type  = "Direct"
  }
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      criticality = {
        date_format = null
        default     = null
        description = "Service criticality level"
        enum        = ["low", "medium", "high", "critical"]
        enum_colors = {
          "critical" = "red"
          "high"     = "orange"
          "low"      = "turquoise"
          "medium"   = "yellow"
        }
        format              = null
        icon                = "Alert"
        max_length          = null
        min_length          = null
        pattern             = null
        required            = false
        spec                = null
        spec_authentication = null
        title               = "Criticality"
      }
    }
  }
  relations = {
    github_repository = {
      description = null
      many        = false
      required    = false
      target      = "githubRepository"
      title       = "GitHub Repository"
    }
    sonar_project = {
      description = null
      many        = false
      required    = false
      target      = "sonarQubeProject"
      title       = "Sonar Project"
    }
  }
  mirror_properties = {
    critical_sonar_bugs = {
      path  = "sonar_project.open_critical_bugs"
      title = "Critical Sonar Bugs"
    }
    critical_sonar_vulnerabilities = {
      path  = "sonar_project.open_critical_vulnerabilities"
      title = "Critical Sonar Vulnerabilities"
    }
    github_codeowners = {
      path  = "github_repository.codeowners"
      title = "Code Owners"
    }
    github_default_branch = {
      path  = "github_repository.defaultBranch"
      title = "Default Branch"
    }
    github_description = {
      path  = "github_repository.description"
      title = "Description"
    }
    github_gitignore = {
      path  = "github_repository.gitignore"
      title = "Git Ignore"
    }
    github_language = {
      path  = "github_repository.language"
      title = "Programming Language"
    }
    github_last_push = {
      path  = "github_repository.last_push"
      title = "Last Repository Push"
    }
    github_pr_template = {
      path  = "github_repository.pr_template"
      title = "PR Template"
    }
    github_readme = {
      path  = "github_repository.readme"
      title = "README"
    }
    github_repository_id = {
      path  = "github_repository.$identifier"
      title = "Repo ID"
    }
    github_url = {
      path  = "github_repository.url"
      title = "Repository URL"
    }
    github_visibility = {
      path  = "github_repository.visibility"
      title = "Visibility"
    }
    last_sonar_analysis = {
      path  = "sonar_project.lastAnalysisDate"
      title = "Last Sonar Analysis"
    }
    sonar_critical_code_smells = {
      path  = "sonar_project.open_critical_codesmell"
      title = "Sonar Critical CodeSmells"
    }
    sonar_project_name = {
      path  = "sonar_project.$title"
      title = "Sonar Project Name"
    }
  }
  calculation_properties = {
    deploy_freq_tier = {
      calculation = "if (.properties.total_deployments == null or .properties.total_deployments == 0) then \"Low\" else if (.properties.deployment_frequency // 0) >= 7 then \"Elite\" elif (.properties.deployment_frequency // 0) >= 1 then \"High\" elif (.properties.deployment_frequency // 0) >= 0.25 then \"Medium\" else \"Low\" end end"
      colorized   = true
      colors = {
        "Elite"  = "lime"
        "High"   = "blue"
        "Low"    = "red"
        "Medium" = "orange"
      }
      date_format         = null
      description         = "DORA deployment frequency tier (from production deployments)"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Deployment Frequency"
      type                = "string"
    }
    github_cycle_time_trend = {
      calculation = "((.properties.github_pr_cycle_time // 0) - (.properties.github_pr_cycle_time_weekly // 0)) as $diff | if $diff > 0 then \"Improving\" elif $diff < 0 then \"Degrading\" else \"Stable\" end"
      colorized   = true
      colors = {
        "Degrading" = "red"
        "Improving" = "green"
        "Stable"    = "blue"
      }
      date_format         = null
      description         = "Weekly vs monthly PR cycle time"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "PR Cycle Time Trend"
      type                = "string"
    }
    github_days_since_last_push = {
      calculation         = "if .properties.github_last_push != null then ((now - (.properties.github_last_push[0:19] + \"Z\" | fromdateiso8601)) / 86400 | floor) else 9999 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Number of days since the last code push"
      format              = null
      icon                = "Clock"
      spec                = null
      spec_authentication = null
      title               = "Days Since Last Push"
      type                = "number"
    }
    github_failure_rate_trend = {
      calculation = "((if (.properties.github_workflow_runs_30d != null and .properties.github_workflow_runs_30d != 0) then ((.properties.github_failed_workflow_runs_30d // 0) / .properties.github_workflow_runs_30d) * 100 | floor else 0 end) - (if (.properties.github_workflow_runs_7d != null and .properties.github_workflow_runs_7d != 0) then ((.properties.github_failed_workflow_runs_7d // 0) / .properties.github_workflow_runs_7d) * 100 | floor else 0 end)) as $diff | if $diff > 0 then \"Improving\" elif $diff < 0 then \"Degrading\" else \"Stable\" end"
      colorized   = true
      colors = {
        "Degrading" = "red"
        "Improving" = "green"
        "Stable"    = "blue"
      }
      date_format         = null
      description         = "Weekly failure rate vs monthly average"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Workflow Failure Rate Trend"
      type                = "string"
    }
    github_lead_time_tier = {
      calculation = "if (.properties.github_lead_time_for_change == null) then \"Low\" elif .properties.github_lead_time_for_change <= 24 then \"Elite\" elif .properties.github_lead_time_for_change <= 168 then \"High\" elif .properties.github_lead_time_for_change <= 720 then \"Medium\" else \"Low\" end"
      colorized   = true
      colors = {
        "Elite"  = "lime"
        "High"   = "blue"
        "Low"    = "red"
        "Medium" = "orange"
      }
      date_format         = null
      description         = "DORA lead time for changes tier (from GitHub PR cycle time)"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Lead Time for Changes (GitHub)"
      type                = "string"
    }
    github_monthly_workflow_failure_rate = {
      calculation         = "if (.properties.github_workflow_runs_30d != null and .properties.github_workflow_runs_30d != 0) then ((.properties.github_failed_workflow_runs_30d // 0) / .properties.github_workflow_runs_30d) * 100 | floor else 0 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of workflow runs that failed in the last 30 days"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Monthly Workflow Failure Rate (%)"
      type                = "number"
    }
    github_stale_pr_share_percent = {
      calculation         = "if (.properties.github_open_prs != null and .properties.github_open_prs != 0) then (.properties.github_stale_prs_7d / .properties.github_open_prs) * 100 else 0 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of open PRs that are older than 7 days"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Stale PR Share (%)"
      type                = "number"
    }
    github_throughput_trend = {
      calculation = "((.properties.github_merged_prs_last_week // 0) * 30 - (.properties.github_merged_prs_last_month // 0) * 7) as $diff | if $diff > 0 then \"Improving\" elif $diff < 0 then \"Degrading\" else \"Stable\" end"
      colorized   = true
      colors = {
        "Degrading" = "red"
        "Improving" = "green"
        "Stable"    = "blue"
      }
      date_format         = null
      description         = "Weekly vs monthly PR throughput rate"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "PR Throughput Trend"
      type                = "string"
    }
    github_weekly_workflow_failure_rate = {
      calculation         = "if (.properties.github_workflow_runs_7d != null and .properties.github_workflow_runs_7d != 0) then ((.properties.github_failed_workflow_runs_7d // 0) / .properties.github_workflow_runs_7d) * 100 | floor else 0 end"
      colorized           = null
      colors              = null
      date_format         = null
      description         = "Percentage of workflow runs that failed in the last 7 days"
      format              = null
      icon                = "DefaultProperty"
      spec                = null
      spec_authentication = null
      title               = "Weekly Workflow Failure Rate (%)"
      type                = "number"
    }
  }
}

resource "port_blueprint" "workload" {
  identifier                    = "workload"
  title                         = "Workload"
  icon                          = "Deployment"
  description                   = null
  create_catalog_page           = true
  force_delete_entities         = false
  include_in_global_search      = null
  kafka_changelog_destination   = null
  webhook_changelog_destination = null
  ownership = {
    path  = "service"
    title = null
    type  = "Inherited"
  }
  properties = {
    array_props   = null
    boolean_props = null
    number_props  = null
    object_props  = null
    string_props = {
      version = {
        date_format         = null
        default             = null
        description         = "The version of the running service in this environment"
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
    }
  }
  relations = {
    environment = {
      description = null
      many        = false
      required    = false
      target      = "environment"
      title       = "Environment"
    }
    k8s_workload = {
      description = null
      many        = false
      required    = false
      target      = "k8s_workload"
      title       = "K8s Workload"
    }
    service = {
      description = null
      many        = false
      required    = false
      target      = "service"
      title       = "Service"
    }
  }
  mirror_properties = {
    running_replicas = {
      path  = "k8s_workload.availableReplicas"
      title = "Running Replicas"
    }
    wanted_replicas = {
      path  = "k8s_workload.replicas"
      title = "Wanted Replicas"
    }
    workload_health = {
      path  = "k8s_workload.isHealthy"
      title = "Workload Health"
    }
    workload_identifier = {
      path  = "k8s_workload.$identifier"
      title = "Workload identifier"
    }
  }
  calculation_properties = null
}

