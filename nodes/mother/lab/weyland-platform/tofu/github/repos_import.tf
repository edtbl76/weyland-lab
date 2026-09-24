# Brownfield import of repos onboarded after the B138 sweep. OpenTofu treats an import block for a resource
# already in state as a no-op, so this is safe to keep after the first `tofu apply` has imported it.
import {
  to = github_repository.OJayFloyd
  id = "OJayFloyd"
}
