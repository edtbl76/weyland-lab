---
id: local-development-environment
tags: [methodology, developer-experience, backend, frontend]
surfaces-at: [application-design, infrastructure-design]
related: [containers, developer-experience, ci-cd, environment-management]
complexity: foundational
---

# Local Development Environment

## What It Is
The setup, tooling, and practices that allow a developer to run the full application stack on their own machine for development and debugging. A good local development environment is fast to set up, produces identical results across all developer machines, and mirrors the production environment closely enough to catch real issues before they reach CI. The most common cause of "works on my machine" bugs is an inconsistent local environment — different OS versions, different runtime versions, missing services, or different configuration values.

## When to Apply
- Every software project with more than one developer
- Projects where new developers need to be productive quickly
- Any service with external dependencies (databases, queues, caches) that need to be available locally
- Teams experiencing "works on my machine" issues

## Key Concepts
- **Dev Containers**: Containerized development environments defined in `.devcontainer/devcontainer.json`. VS Code and GitHub Codespaces support Dev Containers natively — the editor runs inside the container with the correct runtime, tools, and extensions pre-installed. Every developer gets an identical environment regardless of their host OS
- **Docker Compose for Local Services**: Define the full local dependency stack (PostgreSQL, Redis, Kafka, etc.) in `docker-compose.yml`. A single `docker compose up` starts all required services. Developers never manually install databases or configure local services
- **Runtime Version Management**: Use version managers to pin runtime versions per project:
  - Node.js: `nvm` with `.nvmrc` or `volta` with `package.json`
  - Python: `pyenv` with `.python-version` or `mise`
  - Go, Rust, Java: `mise` (formerly rtx) supports multiple runtimes
  - Tool versions file (`.tool-versions`) committed to version control ensures consistency
- **Environment Variables for Local Config**: Local configuration (database URLs, API keys for development) stored in `.env` files that are gitignored. Provide a `.env.example` file committed to the repo with all required variable names and safe placeholder values. New developers copy `.env.example` to `.env` and fill in values
- **Makefile / Task Runners**: A `Makefile` or `Taskfile.yaml` with standard targets (`make setup`, `make run`, `make test`, `make lint`) documents and automates common developer workflows. New developers run `make setup` and are productive within minutes
- **Local vs. Production Parity**: Local environments should use the same database engine as production (PostgreSQL, not SQLite), the same message broker, and the same runtime version. Using different services locally masks bugs that will only appear in production
- **Seeding and Test Data**: Provide seed scripts that populate the local database with realistic test data. Developers should not need to manually create test records for every feature they work on
- **Hot Reload**: Development servers that automatically reload on file changes (webpack dev server, uvicorn `--reload`, Air for Go) dramatically reduce the iteration loop for local development
- **Troubleshooting Documentation**: The project README should document the setup process, common problems, and how to reset the local environment. Runbooks should be updated every time a new developer encounters a setup problem

## In Practice
Method projects use Docker Compose for all local service dependencies — databases, queues, and caches. Dev Containers are used for projects where onboarding speed matters. `.nvmrc` and `.python-version` files pin runtime versions. A `Makefile` exposes standard targets for setup, run, test, and lint. `.env.example` is committed to the repo; `.env` is gitignored. A seeded local database is available via `make seed`.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Local Development Environment**: The standard for a good local dev environment is: a new developer can clone the repo, run one command, and have a working local stack within 15 minutes. Dev Containers and Docker Compose make this achievable. Use `.tool-versions` or runtime-specific version files to pin runtimes — runtime version drift is a constant source of subtle bugs. Never use different services locally than in production (no SQLite in dev, PostgreSQL in prod). Commit a `.env.example` with all required variable names — a missing environment variable discovered at runtime is a preventable onboarding failure. → `engineering-knowledge-repository/local-development-environment.md`

## Related Entries
- [Containers](containers.md) — containers are the foundation of consistent local development environments
- [Developer Experience](developer-experience.md) — local environment quality is a core developer experience concern
- [CI/CD](ci-cd.md) — local environment parity with CI prevents "passes locally, fails in CI" issues
- [Environment Management](environment-management.md) — local is the first tier in the environment promotion chain
