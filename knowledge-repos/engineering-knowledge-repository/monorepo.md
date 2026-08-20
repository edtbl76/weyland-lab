---
id: monorepo
tags: [methodology, developer-experience, deployment]
surfaces-at: [application-design, infrastructure-design]
related: [micro-frontends, microservices, trunk-based-development, modular-monolith]
complexity: intermediate
---

# Monorepo

## What It Is
A version control strategy where multiple projects, packages, services, or applications are stored in a single repository. A monorepo is not a monolith — it can contain many independently deployable services; they just share source control, build tooling, and dependency management. Used by Google, Meta, Microsoft, and Spotify for their entire codebases.

## When to Apply
- Multiple related projects that share code — shared libraries, design systems, shared utilities — benefit from atomic changes and unified versioning
- Teams that want to enforce consistent tooling, linting, and CI across all projects
- Frontend + backend teams that work on closely related code and want to make cross-cutting changes atomically
- Organizations building platforms or SDKs with multiple client libraries

## When Not to Apply
- Completely unrelated projects — sharing a repo adds overhead without the cross-cutting benefit
- Teams without build tooling that supports incremental builds and affected-only CI — a naive monorepo with one big CI pipeline doesn't scale
- Organizations where different project teams have genuinely different toolchain and governance requirements

## Key Concepts
- **Monorepo ≠ Monolith**: Services in a monorepo are still independently deployable — the repo is shared, not the runtime
- **Affected-Only Builds**: Good monorepo tooling runs tests and builds only for packages affected by a change — prevents rebuilding everything on every commit
- **Caching**: Build caches (local and remote) allow teams to skip work already done — critical for large monorepos
- **Tools**: Nx (JavaScript/TypeScript), Turborepo (JavaScript), Bazel (polyglot), Gradle multi-project (JVM), Cargo workspaces (Rust)
- **Dependency Management**: All packages share a root dependency tree — consistent versions across the repo
- **Code Ownership**: `CODEOWNERS` files and module ownership boundaries define which teams own which parts of the monorepo

## In Practice
Monorepos are increasingly common in Method engagements for full-stack JavaScript/TypeScript projects (Nx is the standard recommendation) and for organizations building shared libraries alongside their applications. The biggest risk is naive CI configuration — without affected-only pipeline execution, a monorepo's CI time grows linearly with project count. Invest in Nx or Turborepo tooling upfront.

## Engineering Knowledge
💡 **Engineering Knowledge — Monorepo**: One repo, many projects — not to be confused with one runtime. Monorepos enable atomic cross-cutting changes, shared tooling, and consistent dependency versions. The failure mode is naive CI: without affected-only builds and caching (Nx, Turborepo), every PR rebuilds everything. For JavaScript/TypeScript stacks, Nx is the standard. Great for frontend+backend teams building closely related systems. → `engineering-knowledge-repository/architectural-styles/monorepo.md`

## Related Entries
- [Micro-Frontends](micro-frontends.md) — monorepo is a common code organization strategy for micro-frontend projects
- [Trunk-Based Development](../methodologies/trunk-based-development.md) — monorepos and trunk-based development pair naturally
- [Modular Monolith](modular-monolith.md) — a modular monolith typically lives in a monorepo; microservices may use a monorepo or polyrepo
