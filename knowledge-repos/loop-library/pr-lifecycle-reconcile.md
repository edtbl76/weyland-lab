---
id: pr-lifecycle-reconcile
title: The PR lifecycle reconcile
category: Operations
description: Give every open dependabot and image-bump PR across the watched repos a verdict, and act on it, without ever merging a stale or regressive bump.
terminal_condition: Every managed open PR has a verdict from check-pr-lifecycle.sh, every MERGEABLE, STALE and SUPERSEDED action is taken or listed for the owner, and every NEEDS-HUMAN PR is reported with its reason.
source: docs/runbooks/pr-lifecycle.md (Resolving open PRs — check-pr-lifecycle.sh)
---

## Prompt

Reconcile the open managed PRs ({{repo_or_all}}).

1. Run the advisory command from `docs/runbooks/pr-lifecycle.md` (`bash scripts/check-pr-lifecycle.sh`, or with
   `--repo` for one repo). It mutates nothing.
2. Read each verdict:
   - STALE: recreate it (`@dependabot recreate`); never merge a stale branch, it can downgrade pins main already fixed;
   - SUPERSEDED: close it;
   - MERGEABLE: merge it only with the owner's go-ahead (the owner handles git), or let the nightly reconcile do it;
   - NEEDS-HUMAN: read the reason, especially a REGRESSIVE diff that lowers a pinned version, and report it.
3. Never trust GitHub's mergeable flag alone; the script reads the compare API and the diff for a reason.

Stop when the terminal condition holds. Report counts per verdict and every PR that needs the owner.
