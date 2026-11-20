# Brownfield import of repos onboarded after the B138 sweep. OpenTofu treats an import block for a resource
# already in state as a no-op, so this is safe to keep after the first `tofu apply` has imported it.
import {
  to = github_repository.OJayFloyd
  id = "OJayFloyd"
}

import {
  to = github_repository.grkit
  id = "grkit"
}

# 2026-11-20: Skeets (the time-and-goals assistant) and the NEW, parked MyBodyGraph (health metrics), both created
# via the GitHub API on the owner's instruction after the old MyBodyGraph was renamed to MyBodyGraph-2026-archive.
import {
  to = github_repository.Skeets
  id = "Skeets"
}

import {
  to = github_repository.MyBodyGraph
  id = "MyBodyGraph"
}
