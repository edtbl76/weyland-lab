---
id: dependency-management
tags: [methodology, developer-experience, deployment, security, backend]
surfaces-at: [application-design, infrastructure-design]
related: [semantic-versioning, ci-cd, artifact-management, supply-chain-security]
complexity: foundational
---

# Dependency Management

## What It Is
The practices for declaring, resolving, updating, and securing the third-party libraries and packages that an application depends on. Every production application has dozens to hundreds of transitive dependencies — each with its own version history, CVEs, and upgrade cadence. Good dependency management keeps builds reproducible (same versions every time), keeps dependencies up to date (to avoid accumulating CVE debt), and prevents dependency confusion attacks (pulling the wrong package from a public registry).

## When to Apply
- Every software project with external dependencies (i.e., all of them)
- Before deploying to production (scan dependencies for known CVEs)
- During regular maintenance (automated dependency update PRs)
- When evaluating third-party packages (assess maintenance health and license)

## Key Concepts
- **Lockfiles**: Package managers generate lockfiles (`package-lock.json`, `poetry.lock`, `Pipfile.lock`, `go.sum`, `Cargo.lock`) that pin exact transitive dependency versions. Commit lockfiles to version control — they ensure every developer and every CI build resolves the same dependency graph. Without lockfiles, builds are not reproducible
- **Version Constraints**:
  - *Pinned* (`==1.2.3`): Exact version. Maximum reproducibility; requires manual updates. Appropriate for deployed applications
  - *Flexible* (`^1.2.0`, `~1.2.0`): Allow compatible updates. Appropriate for libraries to avoid version conflicts in consumer applications
- **Direct vs. Transitive Dependencies**: Direct dependencies are what you explicitly declare. Transitive dependencies are what your dependencies depend on — often 10x more numerous. Both are attack surface
- **Automated Updates**:
  - *Dependabot* (GitHub): Automatically opens PRs to update dependencies when new versions are available. Integrates with GitHub Security Advisories for CVE-triggered updates
  - *Renovate Bot*: More configurable than Dependabot; supports grouping, automerge rules, custom schedules
  - Configure to auto-merge patch updates; require review for minor and major updates
- **CVE Scanning**:
  - Audit dependencies against known vulnerability databases: `npm audit`, `pip-audit`, `bundler-audit`, Snyk, OWASP Dependency-Check
  - Run in CI — fail builds on critical CVEs. Don't wait for scheduled scans
  - Distinguish critical/high from low/medium — don't let noise drown out real vulnerabilities
- **License Compliance**: Third-party dependencies have licenses. GPL in a commercial product may be a legal issue. Scan with `license-checker`, FOSSA, or Snyk. Define an allowlist of approved licenses
- **Dependency Confusion**: An attack where a private package name is registered on a public registry, causing the build tool to pull the malicious public version instead of the internal one. Mitigations: scope packages (`@company/my-package`), configure registry resolution order, use private registry proxies
- **Minimal Dependencies**: Every dependency is a liability — maintenance burden, security surface, and upgrade cost. Prefer solutions in the standard library. Evaluate dependency health: last commit date, issue response time, download counts, CVE history

## In Practice
Method projects use lockfiles committed to version control. Dependabot is enabled on all GitHub repositories with weekly minor/patch updates and auto-merge for patch-only PRs. Snyk runs in CI and blocks on critical CVEs. License scanning via FOSSA runs monthly. Internal packages are scoped (`@method/package-name`) to prevent dependency confusion.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Dependency Management**: Commit lockfiles — a project without a lockfile has non-reproducible builds and is one dependency update away from a broken deploy. Enable automated dependency update PRs (Dependabot, Renovate) — manually reviewing dep updates is how CVE debt accumulates to 200 vulnerabilities. Run `npm audit` / `pip-audit` / Snyk in CI and fail on critical CVEs. Minimize your dependency count — every new dependency is a supply chain risk, a maintenance burden, and a potential CVE. Prefer scoped package names for internal libraries to prevent dependency confusion attacks. → `engineering-knowledge-repository/dependency-management.md`

## Related Entries
- [Semantic Versioning](semantic-versioning.md) — package managers use semver to resolve compatible dependency versions
- [CI/CD](ci-cd.md) — dependency vulnerability scanning runs as a CI gate
- [Artifact Management](artifact-management.md) — private package registries provide a controlled dependency distribution channel
- [Supply Chain Security](supply-chain-security.md) — dependency management is a primary supply chain security concern
