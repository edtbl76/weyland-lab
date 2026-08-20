---
id: semantic-versioning
tags: [methodology, deployment, developer-experience, backend]
surfaces-at: [application-design, infrastructure-design]
related: [artifact-management, api-versioning, ci-cd, dependency-management]
complexity: foundational
---

# Semantic Versioning

## What It Is
A versioning convention that encodes the type of change in the version number itself: `MAJOR.MINOR.PATCH`. Breaking changes increment MAJOR; backward-compatible new features increment MINOR; backward-compatible bug fixes increment PATCH. Semantic versioning (semver) makes dependency management tractable — consumers know whether an upgrade is safe without reading every changelog entry. It is the universal versioning standard for libraries, APIs, and packages.

## When to Apply
- Any library, SDK, or package published for others to consume
- Public or partner-facing APIs
- Internal shared libraries used by multiple services
- Any artifact where downstream consumers need to understand upgrade risk

## Key Concepts
- **Version Format**: `MAJOR.MINOR.PATCH[-prerelease][+build]`
  - `1.0.0` — stable release
  - `1.2.3` — patch release (bug fix)
  - `1.3.0` — minor release (new feature, backward compatible)
  - `2.0.0` — major release (breaking change)
  - `1.0.0-alpha.1`, `1.0.0-rc.1` — pre-release labels
- **MAJOR (breaking)**: Any change that breaks existing consumers — removed endpoints, changed method signatures, renamed required fields, changed behavior contracts
- **MINOR (additive)**: New functionality that existing consumers don't need to adopt — new endpoints, optional parameters, new response fields. Old code still works
- **PATCH (fix)**: Bug fixes, performance improvements, security patches — no API surface change. Consumers should upgrade freely
- **Version 0.x.x**: Major version 0 means the API is unstable and breaking changes may happen in any minor release. Signal: "not yet committed to stability"
- **Pre-release Labels**: `-alpha`, `-beta`, `-rc` (release candidate) signal stability level. Package managers may not install pre-release versions by default
- **Dependency Resolution**: Package managers (npm, pip, Maven) use semver to resolve compatible versions:
  - `^1.2.3` — any `1.x.x >= 1.2.3` (caret: allow minor/patch updates)
  - `~1.2.3` — any `1.2.x >= 1.2.3` (tilde: allow only patch updates)
  - `1.2.3` — exact version pin
- **Changelog Practice**: Every version bump should correspond to a CHANGELOG entry describing what changed and why. Tools: `conventional-commits` + `semantic-release` automate version bumping and changelog generation from commit messages
- **Automated Versioning**: Conventional commit format (`feat:`, `fix:`, `BREAKING CHANGE:`) allows tools like `semantic-release` and `release-please` to determine the next version and generate changelogs automatically from commit history
- **CalVer**: An alternative convention using calendar dates (`YYYY.MM.DD` or `YYYY.MINOR`). Used by Ubuntu, Pip, and some data projects where "when it was released" matters more than "what kind of change it was"

## In Practice
Method uses semantic versioning for all internal shared libraries and public APIs. Conventional commits are enforced via commit linting in CI. `semantic-release` runs in CI to automatically determine the next version, tag the release, and generate the CHANGELOG. Major version bumps require a migration guide. API versioning follows semver for library clients; URL-based versioning (`/v1/`, `/v2/`) is used for HTTP APIs.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Semantic Versioning**: Major version bumps are a promise to consumers that they will need to migrate — take them seriously and provide a migration guide. Use conventional commits (`feat:`, `fix:`, `BREAKING CHANGE:`) to make version determination automatable — this removes judgment calls and human error from versioning. Don't stay on `0.x.x` indefinitely if the API is stable; `0.x` signals instability and consumers will avoid it. Lock transitive dependencies in deployed applications (use lockfiles); use flexible semver ranges in libraries. → `engineering-knowledge-repository/semantic-versioning.md`

## Related Entries
- [Artifact Management](artifact-management.md) — artifact version tags follow semantic versioning conventions
- [API Versioning](api-versioning.md) — API versioning strategies build on semver principles for managing breaking changes
- [CI/CD](ci-cd.md) — CI pipelines automate version bumping and changelog generation via conventional commits
- [Dependency Management](dependency-management.md) — package managers use semver to resolve compatible dependency versions
