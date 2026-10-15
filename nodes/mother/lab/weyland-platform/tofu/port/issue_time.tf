# B185 — time per Linear issue: agent session time + lead and cycle time (lane 1), and the owner's own time from
# ActivityWatch and Clockify (lane 2, owner_time.py).
#
# The blueprint is tofu (this file); ENTITIES are written by
# nodes/mother/lab/weyland-platform/scripts/issue_time_report.py --port (run by scripts/issue-time.sh --port after the
# ai-session producer), which also upserts the `time_per_issue` dashboard from pages/time_per_issue.json. The time
# lives BESIDE the Linear integration's `linearIssue` (a relation), not on it: linearIssue is integration-owned and
# revised by the integration on upgrade (docs/runbooks/port.md § What is deliberately UI-managed).
# See docs/runbooks/issue-time.md.

resource "port_blueprint" "issue_time" {
  calculation_properties      = null
  create_catalog_page         = true
  description                 = "Agent and owner time per Linear issue, with lead and cycle time (B185)."
  force_delete_entities       = false
  icon                        = "Clock"
  identifier                  = "issue_time"
  include_in_global_search    = null
  kafka_changelog_destination = null
  mirror_properties           = null
  ownership                   = null
  title                       = "Issue Time"
  properties = {
    array_props = null
    boolean_props = {
      unmapped = {
        default     = null
        description = "a backlog number that matches no single Linear issue: shown under the B number, never guessed"
        icon        = null
        required    = false
        title       = "Unmapped"
      }
    }
    number_props = {
      agent_hours = {
        default     = null
        description = "active main-thread hours attributed to this issue (gaps over 5 min are idle)"
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Agent hours"
      }
      sessions = {
        default     = null
        description = "Claude Code sessions that spent time on it"
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Sessions"
      }
      output_tokens = {
        default     = null
        description = "output tokens, subagents included, counted once per message"
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Output tokens"
      }
      api_equiv_usd = {
        default     = null
        description = "what pay-per-use API would have cost; on the subscription, $0 changes hands"
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "API-equivalent (USD)"
      }
      lead_days = {
        default     = null
        description = "completedAt − createdAt; empty while open"
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Lead time (days)"
      }
      cycle_days = {
        default     = null
        description = "completedAt − the earlier of Linear startedAt and the first agent activity before completion"
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Cycle time (days)"
      }
      owner_aw_hours = {
        default     = null
        description = "B185 lane 2: the owner's own active time on it, from ActivityWatch (Linear tab or a window naming it; AFK excluded). Empty = not collected"
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Owner hours (ActivityWatch)"
      }
      owner_clockify_hours = {
        default     = null
        description = "B185 lane 2: the owner's Clockify timer time on it (the extension's [EMA-###] entries). Empty = Clockify not configured"
        enum        = null
        enum_colors = null
        icon        = null
        maximum     = null
        minimum     = null
        required    = false
        title       = "Owner hours (Clockify)"
      }
    }
    object_props = null
    string_props = {
      backlog = {
        date_format         = null
        default             = null
        description         = "docs/backlog.md number (B###)"
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
        title               = "Backlog"
      }
      first_agent_at = {
        date_format         = null
        default             = null
        description         = "first attributed agent activity still on record (transcripts are pruned after ~30 days)"
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
        title               = "First agent activity"
      }
    }
  }
  relations = {
    issue = {
      description = "the Linear issue (integration-owned linearIssue)"
      many        = false
      required    = false
      target      = "linearIssue"
      title       = "Linear issue"
    }
  }
}
