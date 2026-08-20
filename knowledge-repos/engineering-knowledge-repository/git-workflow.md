---
id: git-workflow
tags: [methodology, developer-experience, backend, frontend]
surfaces-at: [application-design]
related: [trunk-based-development, ci-cd, code-review-practices, feature-flags, monorepo]
complexity: foundational
---

# Git Workflow

## What It Is
The branching strategy and conventions a team follows for how code moves from individual development through review and into the main branch. The right git workflow reduces merge conflicts, keeps the main branch releasable, and makes it clear how and when code gets deployed. The wrong workflow causes integration delays, long-running divergent branches, and painful merges. Three dominant strategies are in use: Trunk-Based Development, GitHub Flow, and Gitflow — each with different tradeoffs around release cadence and team size.

## When to Apply
- Every team using Git (i.e., all of them)
- When establishing a new project or onboarding a new team
- When a team is experiencing frequent merge conflicts or integration delays

## Key Concepts
- **Trunk-Based Development (TBD)**: All developers commit directly to `main` (or via very short-lived branches, < 1 day). Continuous integration runs on every commit. The main branch is always deployable. Feature flags gate incomplete features. Best for: high-velocity teams, mature CI/CD, teams comfortable with feature flags. See the dedicated [Trunk-Based Development](trunk-based-development.md) entry
- **GitHub Flow**: A simplified branching model — create a feature branch from `main`, open a PR, merge back to `main` after review, deploy immediately. One environment, one main branch. No release branches. Best for: teams shipping continuously, SaaS products, small-to-medium teams
  - Branch: `feature/description` or `fix/description`
  - PR → review → merge → deploy
  - Main is always deployable
- **Gitflow**: Two long-lived branches (`main` for production, `develop` for integration) plus feature, release, and hotfix branches. Suited for scheduled releases (mobile apps, versioned libraries) where a release requires stabilization time. Common in Java/Maven ecosystems
  - `feature/*` branches off `develop`
  - `release/*` branches off `develop` for stabilization, merges to `main` + `develop`
  - `hotfix/*` branches off `main` for urgent production fixes
  - Cons: Complex, slow integration, long-lived branches cause merge conflicts. Not recommended for services with continuous deployment
- **Conventional Branch Naming**: Use consistent prefixes: `feature/`, `fix/`, `chore/`, `docs/`. Makes branch purpose clear in PR lists and makes cleanup scripts simple
- **Commit Message Conventions**: Conventional Commits format (`feat:`, `fix:`, `docs:`, `chore:`, `BREAKING CHANGE:`) enables automated changelog generation, semantic versioning, and release automation. Enforced via commitlint in CI or pre-commit
- **Branch Lifetime**: Long-lived feature branches cause merge conflicts and delayed integration. Branches should be merged within days, not weeks. If a feature is too large to merge in a few days, use feature flags to gate incomplete work and merge the partial implementation to main
- **Merge vs. Rebase vs. Squash**:
  - *Merge commits*: Preserve full branch history; creates a merge commit in main's history
  - *Rebase*: Linear history; rewrites branch commits to apply cleanly on top of main. Cleaner history; rewrites commit SHAs (never rebase public branches)
  - *Squash merge*: Collapses all branch commits into one commit on main. Clean history; loses individual commit context from the branch
- **Protected Branches**: Require PR reviews and passing CI before merging to `main`. GitHub branch protection rules enforce this. Never push directly to main in a team environment

## In Practice
Method uses GitHub Flow for all service development — short-lived feature branches, PRs with at least one reviewer, and direct merge to main. Conventional commits are enforced via commitlint. Main is protected with required CI checks and one required reviewer. Feature flags (LaunchDarkly) gate incomplete features to avoid long-lived branches. Gitflow is used only for versioned library releases.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Git Workflow**: Choose the simplest workflow that fits your release cadence. GitHub Flow (short branches → PR → merge to main → deploy) is correct for most SaaS teams. Gitflow is only justified for products with scheduled versioned releases (mobile apps, libraries) — for everything else, it's complexity without benefit. Long-lived branches are the enemy — they cause merge conflicts and delay integration. Use feature flags to merge incomplete work to main rather than keeping branches open. Enforce conventional commits — it makes versioning and changelog automation possible. → `engineering-knowledge-repository/git-workflow.md`

## Related Entries
- [Trunk-Based Development](trunk-based-development.md) — the highest-velocity variant of git workflow for continuous integration teams
- [CI/CD](ci-cd.md) — CI pipelines trigger on branch events and enforce gates before merge
- [Code Review Practices](code-review-practices.md) — PRs are the primary code review mechanism in branch-based workflows
- [Feature Flags](feature-flags.md) — feature flags enable merging incomplete work to main without exposing it to users
- [Monorepo](monorepo.md) — monorepos require git workflow conventions that handle multiple packages in one repository
