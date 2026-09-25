# stud.io `main` protection — codified 2026-09-25 (import first, then encode; generated with -generate-config-out
# from the live settings, not hand-guessed). stud.io's `main` carries TWO layers, both kept here so neither drifts:
#   1. classic branch protection (github_branch_protection)  — PR required, 0 approvals, stale reviews dismissed.
#   2. the `main` ruleset (github_repository_ruleset)         — the same PR rule; repo admins may bypass.
#
# REMOVED: the required status check `ci/woodpecker/pr/main` (strict). It was satisfiable only while stud.io had its
# own Woodpecker receiving GitHub webhooks. Since B57 moved stud.io CI onto weyland's Woodpecker (2026-08-18), that
# Woodpecker is LAN-only — GitHub cannot deliver PR webhooks to it, it has run ONLY `manual` pipelines on main (15 of
# them), and a manual run reports `ci/woodpecker/manual/...`, never `.../pr/main`. So from 2026-08-18 NO stud.io PR
# (dependabot or human) could satisfy the check: every merge needed an admin bypass (stud.io #122-124, 2026-09-25).
# A check that can never arrive is a forced bypass, not a gate. No replacement is required: the checks that DO arrive
# (DeepSource, CodeRabbit, CodeScene) are third-party and vary per PR — requiring one would rebuild the same trap.
# Real PR gating for stud.io needs PR events reaching Woodpecker, which the LAN cannot do today.

import {
  to = github_branch_protection.stud_io_main
  id = "stud.io:main"
}

import {
  to = github_repository_ruleset.stud_io_main
  id = "stud.io:14534159"
}

resource "github_branch_protection" "stud_io_main" {
  repository_id                   = github_repository.stud_io.node_id
  pattern                         = "main"
  allows_deletions                = false
  allows_force_pushes             = false
  enforce_admins                  = false
  force_push_bypassers            = []
  lock_branch                     = false
  require_conversation_resolution = false
  require_signed_commits          = false
  required_linear_history         = false

  required_pull_request_reviews {
    dismiss_stale_reviews           = true
    dismissal_restrictions          = []
    pull_request_bypassers          = []
    require_code_owner_reviews      = false
    require_last_push_approval      = false
    required_approving_review_count = 0
    restrict_dismissals             = false
  }
  # required_status_checks deliberately ABSENT — see the header.
}

resource "github_repository_ruleset" "stud_io_main" {
  name        = "main"
  repository  = github_repository.stud_io.name
  target      = "branch"
  enforcement = "active"

  bypass_actors {
    actor_id    = 5 # the built-in "Admin" repository role
    actor_type  = "RepositoryRole"
    bypass_mode = "always"
  }

  conditions {
    ref_name {
      include = ["refs/heads/main"]
      exclude = []
    }
  }

  rules {
    creation                      = false
    deletion                      = false
    non_fast_forward              = false
    required_linear_history       = false
    required_signatures           = false
    update                        = false
    update_allows_fetch_and_merge = false

    pull_request {
      allowed_merge_methods             = ["merge", "squash", "rebase"]
      dismiss_stale_reviews_on_push     = true
      require_code_owner_review         = false
      require_last_push_approval        = false
      required_approving_review_count   = 0
      required_review_thread_resolution = false
    }
  }
}
