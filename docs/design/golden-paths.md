# Golden paths — blessed per-language service templates (B153)

A **golden path** is a blessed, paved-road starting point for a service in a given language + framework.
It is **runnable, ephemeral, and extendable**: it builds a real image, spins up as a **run-to-completion
k8s Job** that exercises itself in-cluster and exits (never a Deployment), and is the **template a real
service is scaffolded from**. Each golden path both (a) replaces the B88 hello fixture as the CI
build-infra probe for its language, and (b) lands already-compliant with the onboarding gates (B154) and
the API lifecycle (B155), so "start a new service" is one command that begins in a DoD-passing state.

## The altitude: one contract, many frameworks

The "one paved road" is the **contract** below — the shape every golden path satisfies. The *framework*
lives beneath that altitude, so a language can have several golden paths (Java: Spring **and** Quarkus
**and** Micronaut) that all conform to the same contract. The onboarding gates + CI lanes check the
CONTRACT, never the framework — frameworks are interchangeable implementations.

### The contract (framework-agnostic)

| Facet | Requirement |
|---|---|
| **HTTP surface** | `GET /health` (liveness) · `GET /ready` (readiness — the SMOKE-gate probe) · `GET /metrics` (Prometheus exposition) · `GET /hello` (a demo endpoint returning a known JSON payload). |
| **Self-test** | a test suite discoverable by the lane's marker (`pom.xml`/`go.mod`/`package.json`/`pyproject.toml`/`Cargo.toml`) + a `selfcheck` (a deliberately-failing test proving the runner propagates failure) + a `coverage-baseline` entry. Replaces the language's hello fixture. |
| **Build** | a multi-stage, non-root, minimal **Dockerfile** buildkit builds to `registry.weyland.lab/golden-<lang>-<framework>`; a `readinessProbe`-compatible `/ready`. |
| **Ephemeral run** | a **k8s Job** (run-to-completion, `restartPolicy: Never`) that starts the built image, hits its own `/ready` + `/hello`, asserts the known payload, and exits 0 — proving the image runs on the real platform — then is torn down. Never a Deployment. |
| **Onboarding declaration** | a commented `applications.yaml` entry (`deployed`/`metrics`/`ingress`/`likec4`/`port_component`) + an `apis.yaml` entry (owner/kind/status/version/spec) + a LikeC4 element, as a TEMPLATE the scaffolder fills — so a scaffolded real service passes `check-onboarding-completeness.sh` + `check-api-lifecycle.sh` by construction. |
| **Observability** | structured logging + `/metrics`; an OTel hook (or a documented stub). |
| **Scaffold seam** | parameterized name/port placeholders so `scripts/new-service.sh <golden-path> <name>` stamps a real service. |

## The locked framework matrix (21 golden paths)

| Language | Frameworks | Lane runner |
|---|---|---|
| **Python** | FastAPI · Flask · Litestar · Django | pytest |
| **Java** | Spring Boot · Quarkus · Micronaut | mvn |
| **Go** | net/http (stdlib) · Gin · Echo · Fiber | go |
| **Rust** | Axum · Actix-web · Rocket | cargo |
| **Node (TS/JS)** | Express · Fastify · NestJS | node |
| **Frontend (React/Next)** | Next.js · Remix · Vite+React · Astro | node |

Frontend golden paths satisfy an adapted contract: `/health`+`/ready` via the framework's server (or a
tiny sidecar route), a build that produces the static/SSR bundle, a smoke that renders the demo route.

## Layout + hello replacement

Golden paths live at `golden-paths/<language>/<framework>/`. Each is lane-discoverable (carries the
marker) and carries a `selfcheck` + a coverage-baseline row. Once a language's golden paths cover it, the
old `tests/lang/<lang>/` hello fixture is retired (the golden path is the leaner replacement — one
artifact that is both the blessed template and the build-infra probe). The lane runners
(`run-lang-tests.sh`, `run-lang-scan.sh`) discover golden paths by the same marker mechanism.

## Ephemeral-Job harness

`k8s/golden-paths/` holds a Job template per golden path (or one parameterized Job). A CronJob or an
on-demand `scripts/run-golden-path-jobs.sh` builds each image (buildkit on mother), applies the Job,
waits for completion, asserts exit 0, and deletes it. This is the "spin up to exercise, then tear down"
loop — it proves the built image runs on the platform without occupying it.

## Build checklist (21) — durable tracking

Legend: ☐ not started · ◐ template built · ● lane-verified · ★ Job-verified + onboarding-decl + hello-retired

**Python** — ● FastAPI *(reference — lane-verified: 4 tests pass, selfcheck fails, coverage 100% baselined, smoke.py serves; ★ pending the in-cluster Job run)* · ☐ Flask · ☐ Litestar · ☐ Django
**Java** — ☐ Spring Boot · ☐ Quarkus · ☐ Micronaut
**Go** — ☐ net/http · ☐ Gin · ☐ Echo · ☐ Fiber
**Rust** — ☐ Axum · ☐ Actix-web · ☐ Rocket
**Node** — ☐ Express · ☐ Fastify · ☐ NestJS
**Frontend** — ☐ Next.js · ☐ Remix · ☐ Vite+React · ☐ Astro

Build order: **FastAPI is the reference** (matches the estate; establishes the contract + Dockerfile +
Job + onboarding-decl + hello-retirement pattern end-to-end). Then the rest roll out per-language in
batches, each conforming to the locked contract.

## Definition of Done (per golden path + the system)

Per path: lane-runs (test + selfcheck + coverage) · buildkit image · ephemeral Job exits 0 · onboarding
declaration template present · hello retired (once the language is covered). System: `golden-paths.md`
(this) + a flow diagram + a demo (the CLI/Job walkthrough RUN) + the scaffolder + backlog/Linear.
