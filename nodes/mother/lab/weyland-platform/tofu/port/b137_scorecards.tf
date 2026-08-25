# B137 — Port scorecards codified 2026-08-24. 8 scorecards, 44 rules of hand-written delivery,
# quality and reliability logic that NOTHING regenerates: no integration owns a scorecard, so if the
# Port org were lost this was gone permanently. That is why these were the highest-value half of B137.
#
# `conditions` are JSON-encoded STRINGS by the provider's own contract ("Each condition object should
# be encoded to a string"), hence jsonencode() rather than nested HCL objects.

resource "port_scorecard" "service_delivery_performance" {
  identifier = "delivery_performance"
  title      = "Delivery Performance"
  blueprint  = "service"
  filter     = null
  rules = [
    {
      identifier  = "github_manageable_open_prs"
      title       = "Open PRs \u2264 8"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<=", "property" : "github_open_prs", "value" : 8 }),
        ]
      }
    },
    {
      identifier  = "github_no_stale_prs"
      title       = "Stale PRs = 0"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "=", "property" : "github_stale_prs_7d", "value" : 0 }),
        ]
      }
    },
    {
      identifier  = "github_cycle_time_under_24h"
      title       = "PR cycle time < 24h"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "github_pr_cycle_time", "value" : 24 }),
        ]
      }
    },
    {
      identifier  = "github_cycle_time_not_degrading"
      title       = "PR cycle time not degrading"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "!=", "property" : "github_cycle_time_trend", "value" : "Degrading" }),
        ]
      }
    },
    {
      identifier  = "github_cycle_time_under_7d"
      title       = "MR cycle time < 7 days"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "github_pr_cycle_time", "value" : 168 }),
        ]
      }
    },
    {
      identifier  = "github_throughput_not_degrading"
      title       = "Throughput not degrading"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "!=", "property" : "github_throughput_trend", "value" : "Degrading" }),
        ]
      }
    },
    {
      identifier  = "github_excellent_open_pr_management"
      title       = "Open PRs \u2264 3"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<=", "property" : "github_open_prs", "value" : 3 }),
        ]
      }
    },
    {
      identifier  = "github_good_open_pr_management"
      title       = "Open PRs \u2264 5"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<=", "property" : "github_open_prs", "value" : 5 }),
        ]
      }
    },
    {
      identifier  = "github_minimal_stale_prs"
      title       = "Stale PRs \u2264 1"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<=", "property" : "github_stale_prs_7d", "value" : 1 }),
        ]
      }
    },
    {
      identifier  = "github_good_throughput"
      title       = "Merged PRs \u2265 5/week"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">=", "property" : "github_merged_prs_last_month", "value" : 20 }),
        ]
      }
    },
    {
      identifier  = "github_low_stale_prs"
      title       = "Stale PR share \u2264 10%"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<=", "property" : "github_stale_pr_share_percent", "value" : 10 }),
        ]
      }
    },
    {
      identifier  = "github_has_merged_prs"
      title       = "Merged PRs \u2265 2/week"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">=", "property" : "github_merged_prs_last_month", "value" : 8 }),
        ]
      }
    },
    {
      identifier  = "github_cycle_time_under_1h"
      title       = "PR cycle time < 1h"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "github_pr_cycle_time", "value" : 1 }),
        ]
      }
    },
    {
      identifier  = "github_excellent_throughput"
      title       = "Merged PRs \u2265 10/week"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">=", "property" : "github_merged_prs_last_month", "value" : 40 }),
        ]
      }
    },
  ]
}

resource "port_scorecard" "service_dora_deploy_freq" {
  identifier = "dora_deploy_freq"
  title      = "Deployment Frequency"
  blueprint  = "service"
  filter     = null
  rules = [
    {
      identifier  = "github_svc_df_medium"
      title       = "Deploys at least monthly (>= 0.25/week)"
      level       = "Bronze"
      description = "DORA Medium tier"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">=", "property" : "deployment_frequency", "value" : 0.25 }),
        ]
      }
    },
    {
      identifier  = "github_svc_df_high"
      title       = "Deploys at least weekly (>= 1/week)"
      level       = "Silver"
      description = "DORA High tier"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">=", "property" : "deployment_frequency", "value" : 1 }),
        ]
      }
    },
    {
      identifier  = "github_svc_df_elite"
      title       = "Deploys at least daily (>= 7/week)"
      level       = "Gold"
      description = "DORA Elite tier"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">=", "property" : "deployment_frequency", "value" : 7 }),
        ]
      }
    },
  ]
}

resource "port_scorecard" "service_dora_lead_time" {
  identifier = "dora_lead_time"
  title      = "Lead Time for Changes"
  blueprint  = "service"
  filter     = null
  rules = [
    {
      identifier  = "github_svc_lt_high"
      title       = "Lead time under 1 week (< 168h)"
      level       = "Silver"
      description = "DORA High tier"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<=", "property" : "github_lead_time_for_change", "value" : 168 }),
        ]
      }
    },
    {
      identifier  = "github_svc_lt_medium"
      title       = "Lead time under 1 month (< 720h)"
      level       = "Bronze"
      description = "DORA Medium tier"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<=", "property" : "github_lead_time_for_change", "value" : 720 }),
        ]
      }
    },
    {
      identifier  = "github_svc_lt_elite"
      title       = "Lead time under 1 day (< 24h)"
      level       = "Gold"
      description = "DORA Elite tier"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<=", "property" : "github_lead_time_for_change", "value" : 24 }),
        ]
      }
    },
  ]
}

resource "port_scorecard" "service_production_readiness" {
  identifier = "production_readiness"
  title      = "Production Readiness"
  blueprint  = "service"
  filter     = null
  rules = [
    {
      identifier  = "github_has_pr_template"
      title       = "Has PR template"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "property" : "github_pr_template" }),
        ]
      }
    },
    {
      identifier  = "github_has_criticality"
      title       = "Has criticality defined"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "property" : "criticality" }),
        ]
      }
    },
    {
      identifier  = "github_has_url"
      title       = "Has repository URL"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "property" : "github_url" }),
        ]
      }
    },
    {
      identifier  = "github_has_readme"
      title       = "Has README"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "property" : "github_readme" }),
        ]
      }
    },
    {
      identifier  = "github_active_repo_30d"
      title       = "Active repo (pushed in last 30 days)"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "github_days_since_last_push", "value" : 30 }),
        ]
      }
    },
    {
      identifier  = "github_has_codeowners"
      title       = "Has CODEOWNERS"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "property" : "github_codeowners" }),
        ]
      }
    },
    {
      identifier  = "github_has_team"
      title       = "Has team assigned"
      level       = "Bronze"
      description = "Service must have a dedicated owning team \u2014 default team does not count"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "property" : "$team" }),
          jsonencode({ "operator" : "doesNotContains", "property" : "$team", "value" : "default-team" }),
          jsonencode({ "operator" : "doesNotContains", "property" : "$team", "value" : "default_team" }),
        ]
      }
    },
    {
      identifier  = "github_has_gitignore"
      title       = "Has .gitignore"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "property" : "github_gitignore" }),
        ]
      }
    },
    {
      identifier  = "github_has_language"
      title       = "Has language defined"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "property" : "github_language" }),
        ]
      }
    },
    {
      identifier  = "github_active_repo_7d"
      title       = "Active repo (pushed in last 7 days)"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "github_days_since_last_push", "value" : 7 }),
        ]
      }
    },
  ]
}

resource "port_scorecard" "service_quality_maturity" {
  identifier = "quality_maturity"
  title      = "Quality Maturity"
  blueprint  = "service"
  filter     = null
  levels = [
    { color = "paleBlue", title = "Basic" },
    { color = "purple", title = "Maturing" },
    { color = "bronze", title = "Bronze" },
    { color = "silver", title = "Silver" },
    { color = "gold", title = "Gold" },
  ]
  rules = [
    {
      identifier  = "lessThen5codesmells"
      title       = "Less than 5 code smells"
      level       = "Bronze"
      description = "The service have less than 5 open critical code smells"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "sonar_critical_code_smells", "value" : 5 }),
        ]
      }
    },
    {
      identifier  = "connectedToSonar"
      title       = "SonarQube Set up for this service"
      level       = "Maturing"
      description = "The service is connected to a sonar project"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "isNotEmpty", "relation" : "sonar_project" }),
        ]
      }
    },
    {
      identifier  = "scanedLastMonth"
      title       = "Scanned by Sonar last month"
      level       = "Silver"
      description = "The service was scanned by sonar in the last month"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "between", "property" : "last_sonar_analysis", "value" : { "preset" : "lastMonth" } }),
        ]
      }
    },
    {
      identifier  = "noOpenCriticalIssues"
      title       = "No open critical issues"
      level       = "Gold"
      description = "The service does not have any open critical issues"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "=", "property" : "sonar_critical_code_smells", "value" : 0 }),
          jsonencode({ "operator" : "=", "property" : "critical_sonar_bugs", "value" : 0 }),
        ]
      }
    },
    {
      identifier  = "lessThen5bugs"
      title       = "Less than 5 bugs"
      level       = "Bronze"
      description = "The service have less than 5 open critical bugs"
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "sonar_critical_code_smells", "value" : 5 }),
        ]
      }
    },
  ]
}

resource "port_scorecard" "service_reliability_health" {
  identifier = "reliability_health"
  title      = "Reliability Health"
  blueprint  = "service"
  filter     = null
  rules = [
    {
      identifier  = "github_failure_rate_under_30"
      title       = "Workflow failure rate < 30%"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "github_monthly_workflow_failure_rate", "value" : 30 }),
        ]
      }
    },
    {
      identifier  = "github_failure_rate_under_15"
      title       = "Workflow failure rate < 15%"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "github_monthly_workflow_failure_rate", "value" : 15 }),
        ]
      }
    },
    {
      identifier  = "github_failure_rate_not_degrading"
      title       = "Workflow failure rate not degrading"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "!=", "property" : "github_failure_rate_trend", "value" : "Degrading" }),
        ]
      }
    },
    {
      identifier  = "github_failure_rate_under_5"
      title       = "Workflow failure rate < 5%"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "<", "property" : "github_monthly_workflow_failure_rate", "value" : 5 }),
        ]
      }
    },
    {
      identifier  = "github_has_workflow_runs"
      title       = "Has workflow runs this month"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">", "property" : "github_workflow_runs_30d", "value" : 0 }),
        ]
      }
    },
  ]
}

resource "port_scorecard" "sonarQubeProject_services_connected" {
  identifier = "services_connected"
  title      = "Services Connected"
  blueprint  = "sonarQubeProject"
  filter     = null
  levels = [
    { color = "red", title = "Not connected" },
    { color = "green", title = "Connected" },
  ]
  rules = [
    {
      identifier  = "connectedToService"
      title       = "Connected To Service"
      level       = "Connected"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">", "property" : "number_of_services_connected", "value" : 0 }),
        ]
      }
    },
  ]
}

resource "port_scorecard" "workload_availability" {
  identifier = "availability"
  title      = "Availability"
  blueprint  = "workload"
  filter     = null
  rules = [
    {
      identifier  = "healthy"
      title       = "Healthy"
      level       = "Bronze"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : "=", "property" : "workload_health", "value" : "Healthy" }),
        ]
      }
    },
    {
      identifier  = "available2"
      title       = "Average Availability"
      level       = "Silver"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">=", "property" : "wanted_replicas", "value" : 2 }),
        ]
      }
    },
    {
      identifier  = "available3"
      title       = "High Availability"
      level       = "Gold"
      description = null
      query = {
        combinator = "and"
        conditions = [
          jsonencode({ "operator" : ">=", "property" : "wanted_replicas", "value" : 3 }),
        ]
      }
    },
  ]
}

