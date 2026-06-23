# weyland-lab repo — codified from the live GitHub repo. Computed fields (etag, fork) + create-only template
# fields (gitignore_template, license_template, source_owner/repo, archive_on_destroy) dropped. Imported.
resource "github_repository" "weyland_lab" {
  name                        = "weyland-lab"
  description                 = ""
  homepage_url                = ""
  visibility                  = "public"
  topics                      = []
  is_template                 = false
  archived                    = false
  auto_init                   = false

  ignore_vulnerability_alerts_during_read = false

  has_issues                  = true
  has_projects                = true
  has_wiki                    = true
  has_discussions             = false
  has_downloads               = true

  allow_merge_commit          = true
  allow_squash_merge          = true
  allow_rebase_merge          = true
  allow_auto_merge            = false
  allow_update_branch         = false
  allow_forking               = true
  delete_branch_on_merge      = false
  web_commit_signoff_required = false

  merge_commit_title          = "MERGE_MESSAGE"
  merge_commit_message        = "PR_TITLE"
  squash_merge_commit_title   = "COMMIT_OR_PR_TITLE"
  squash_merge_commit_message = "COMMIT_MESSAGES"

  security_and_analysis {
    secret_scanning {
      status = "enabled"
    }
    secret_scanning_push_protection {
      status = "enabled"
    }
  }
}
