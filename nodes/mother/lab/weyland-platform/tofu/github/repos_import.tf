# B138 — codify the remaining active repos in IaC (the `iac` coverage lane).
#
# `tofu/github` previously managed only weyland-lab (repo.tf). These `import {}` blocks + a
# `tofu plan -generate-config-out=...` run generate ACCURATE github_repository config straight from the LIVE
# repos — never hand-guessed, per the B137 lesson (a guessed block makes an apply MUTATE the real repo). After
# the import applies, `repos_generated.tf` holds the resource blocks, the coverage guard's `iac` lane sees all
# 8 active repos, and `iac` gets promoted into repos.yaml `enforce`.
#
# midi_real_book is deliberately absent (SoT `status: stale`, `iac: false`). freejack is PRIVATE — the
# GITHUB_TOKEN used for the generate/import run MUST have access to it, or its import fails.
#
# One-time: these blocks can be removed after the import completes (tofu ignores already-imported resources).
# Import id = the bare repository name (the provider's `owner` is edtbl76).

import {
  to = github_repository.Algopedia
  id = "Algopedia"
}

import {
  to = github_repository.ServiceTransformation
  id = "ServiceTransformation"
}

import {
  to = github_repository.emangini_tailwind_nextjs_contentlayer
  id = "emangini-tailwind-nextjs-contentlayer"
}

import {
  to = github_repository.startme_curator
  id = "startme-curator"
}

import {
  to = github_repository.stud_io
  id = "stud.io"
}

import {
  to = github_repository.freejack
  id = "freejack"
}

import {
  to = github_repository.MyBodyGraph
  id = "MyBodyGraph"
}
