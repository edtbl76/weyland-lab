---
# ADR plugin configuration (zircote-plugins/adr v0.2.0, installed as adr@local — B248, ADR-0001).
# Read by /adr:new, /adr:list, /adr:update, /adr:supersede, /adr:search, /adr:export.

adr_paths:
  - docs/adr/

default_format: madr
madr_variant: full

numbering:
  pattern: "4digit"
  start_from: 1

statuses:
  workflow:
    - proposed
    - accepted
    - deprecated
    - superseded
  allow_rejected: true

linking:
  auto_update_superseded: true
  require_supersedes_reason: true

index:
  auto_generate: true
  include_summary: false
  include_status_badge: false
  group_by_status: false

# The owner handles ALL git (AGENTS.md). The plugin must never commit.
git:
  enabled: false
  auto_commit: false

compliance:
  enabled: false
---

# weyland ADR context

- The log is `docs/adr/` (index: `docs/adr/README.md`). How to add, supersede and search, including from harnesses
  that cannot run this plugin: `docs/runbooks/adr.md`.
- `scripts/check-adr.sh` (CI repo-guards) requires, in every ADR: `## Status` (proposed, accepted, deprecated,
  rejected, or `Superseded by [ADR-NNNN](./NNNN-slug.md)`), `## Context and Problem Statement`, `## Considered Options`,
  `## Decision Outcome` and `### Consequences`; numbers 0001.. with no gap; and an index row per file.
- Link the design record, concept verdict or runbook a decision came from instead of copying it. Put the decision's
  date on a `Date: YYYY-MM-DD` line under the status.
