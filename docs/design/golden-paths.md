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

## Lifecycle flow

The golden path is one artifact that flows through the whole paved road — from "start a service" to a
gate-passing, running-on-the-platform deployment. It is also its own language's CI fixture+probe.

```mermaid
flowchart TD
    GP["golden-paths/&lt;lang&gt;/&lt;fw&gt;/<br/>(contract: /health /ready /metrics /hello<br/>+ selfcheck + Dockerfile + .smoke)"]

    GP -->|"scripts/new-service.sh &lt;path&gt; &lt;name&gt;"| SVC["real service<br/>(token rewritten, selfcheck dropped,<br/>onboarding declaration printed)"]
    GP -->|"resolve_fixture()"| FIX["this lane's fixture+probe<br/>(replaces the retired B88 hello app)"]

    subgraph CI["CI lanes (.woodpecker.yml)"]
        direction LR
        FIX --> T["run-lang-tests.sh<br/>fixture passes · selfcheck fails · real projects pass"]
        FIX --> C["coverage-ratchet.sh<br/>no regression vs baseline"]
        FIX --> S["run-lang-scan.sh<br/>eslint/tsc/clippy/… resolve + run (fail-closed)"]
    end

    GP -->|"buildkit (Dockerfile)"| IMG["registry.weyland.lab/golden-&lt;lang&gt;-&lt;fw&gt;"]
    IMG -->|"scripts/run-golden-path-jobs.sh<br/>reads .smoke"| JOB["run-to-completion k8s Job (ns weyland)<br/>start image · curl /ready + /hello · exit 0"]
    JOB -->|"ttlSecondsAfterFinished / delete"| GONE["torn down — proven runnable, occupies nothing"]

    SVC -->|"applications.yaml · apis.yaml · weyland.likec4"| ONB["check-onboarding-completeness.sh<br/>+ check-api-lifecycle.sh pass by construction"]
```

The left path is scaffolding a real service; the right/centre is the golden path proving itself as the
lane fixture and as a buildable, run-to-completion image on the real platform. Both start from the same
directory and the same contract.

## Layout + hello replacement

Golden paths live at `golden-paths/<language>/<framework>/`. Each is lane-discoverable (carries the
marker) and carries a `selfcheck` + a coverage-baseline row. Once a language's golden paths cover it, the
old `tests/lang/<lang>/` hello fixture is retired (the golden path is the leaner replacement — one
artifact that is both the blessed template and the build-infra probe). The lane runners
(`run-lang-tests.sh`, `run-lang-scan.sh`) discover golden paths by the same marker mechanism.

**Fixture-switch — DONE 2026-09-08.** Each lane's fixture is now its golden path, resolved by
`scripts/lib/lang-fixtures.sh` `resolve_fixture()` (shared by `run-lang-tests.sh`, `run-lang-scan.sh`,
`coverage-ratchet.sh`): python→python/fastapi, java→java/spring-boot, go→go/nethttp, rust→rust/axum,
javascript→node/express, typescript→node/nestjs, react→frontend/vite-react, nextjs→frontend/nextjs.
`shell` has no golden path, so it keeps its hello fixture. The `WEYLAND_LANG_FIXTURE_DIR` override
still means `<dir>/<lang>` (the seam the bats guards inject through); only the DEFAULT changed. The
resolved fixture is excluded from real-project discovery so it is counted once. The eight B88 hello
fixtures under `tests/lang/` are retired (shell + `coverage-baseline.tsv` remain).

**Scan-lane hardening (prerequisite, DONE 2026-09-08).** Making golden paths the scan fixtures surfaced
two fail-open bugs in `run-lang-scan.sh`, both fixed + pinned by `scripts/tests/lang-scan-guard.bats`:
(1) `run_tool`'s "missing scanner" guard matched only old npm strings, so current npm's
`npx canceled due to missing packages` read as a finding instead of `LANE BROKEN`; (2) `scan_node`/
`scan_rust`/`scan_java` returned only the LAST tool's status (no `set -e`), masking an earlier missing
scanner — now they aggregate. `scan_node`'s `tsc`/`next lint` are CAPABILITY-driven (tsconfig / a `next`
dep) not lane-driven, so a plain-JS path discovered under the TS/React/Next lanes isn't asked for a
tsconfig or Next. Every golden path carries the estate's eslint config + scan devDeps and scans clean.

## Ephemeral-Job harness

`k8s/golden-paths/` holds a Job template per golden path (or one parameterized Job). A CronJob or an
on-demand `scripts/run-golden-path-jobs.sh` builds each image (buildkit on mother), applies the Job,
waits for completion, asserts exit 0, and deletes it. This is the "spin up to exercise, then tear down"
loop — it proves the built image runs on the platform without occupying it.

## Build checklist (21) — durable tracking

Legend: ☐ not started · ◐ template built · ● lane-verified · ★ Job-verified + onboarding-decl + hello-retired

**Python** — ● FastAPI · ● Flask · ● Litestar · ● Django *(all 4 lane-verified 2026-09-07: 4 tests pass + selfcheck fails + coverage 100% baselined + smoke.py serves; the lane runs fixture + 4 projects green. FastAPI is the reference; the `.coveragerc` (omit test/smoke/selfcheck) keeps coverage on the service code. ★ pending the in-cluster Job run; hello-retirement pending the cross-language fixture-switch.)*
**Java** — ● Spring Boot · ● Quarkus · ● Micronaut *(all 3 verified 2026-09-07 via `mvn test`: 4 contract tests pass + BUILD SUCCESS + `-Pselfcheck` fails; the java lane discovers all 3. Contract via a REST controller/resource + micrometer `/metrics`. Multi-stage Dockerfile (maven→JRE, curl for the smoke) + `smoke.sh` + `.smoke`. ★ pending the in-cluster Job run; java coverage records on the ratchet's first run.)*
**Go** — ● net/http · ● Gin · ● Echo · ● Fiber *(all 4 verified 2026-09-07 on go 1.26 + `-race`: 4 contract tests pass + coverage baselined (86.7/92.3/86.7/91.7) + the `deliberate`-tagged selfcheck fails; go lane discovers all 4. prometheus/client_golang `/metrics`; go.mod/go.sum committed; alpine runtime + `smoke.sh`. Fiber = fasthttp, tested via `app.Test`.)*
**Rust** — ● Axum · ● Actix-web · ● Rocket *(all 3 verified 2026-09-08 on rust:1-slim: 4 contract tests pass + the `#[ignore]` selfcheck fails under `cargo test -- --ignored`; rust lane discovers all 3. prometheus `/metrics` via TextEncoder; Cargo.lock committed; debian-slim runtime + `smoke.sh` (Rocket binds 8080 via ROCKET_* env). Axum tested via tower `oneshot`, Actix via `test::init_service`, Rocket via `local::blocking::Client`.)*
**Node** — ● Express · ● Fastify · ● NestJS *(all 3 verified 2026-09-08 on node:24-alpine, the CI image: 4 contract tests pass + selfcheck exits non-zero + coverage baselined. Three framework-idiomatic test strategies on the one node runner: Express = jest + supertest (100%), Fastify = node:test + `fastify.inject()`, dependency-light (100%), NestJS = @nestjs/testing + supertest via ts-jest (78.31% — Nest's decorator metadata is counted but not unit-testable). `prom-client` `/metrics`; alpine runtime (NestJS: tsc → `dist/`) + `smoke.sh`. package-lock.json committed; node_modules/dist/coverage gitignored. NOTE: the four node lanes (typescript/javascript/react/nextjs) share one repo-wide glob, so each path is discovered under all four — baseline rows are recorded once per path under its semantic lane (express/fastify → javascript, nestjs → typescript); the other lanes auto-record and pass.)*
**Frontend** — ● Next.js · ● Remix · ● Vite+React · ● Astro *(all 4 verified 2026-09-08 on node:24-alpine, the CI image: contract tests pass + selfcheck exits non-zero + coverage 100% baselined, AND each was built + served in-container with the smoke curling `/health` `/ready` `/metrics` `/hello` + the demo route. The adapted frontend contract is met four ways: Next.js (App Router route handlers + SSR page, `output: standalone`), Remix (resource routes + SSR via Remix+Vite, `json()` helper), Vite+React (SPA + a stdlib static server carrying the endpoints — the "sidecar route"), Astro (SSR `@astrojs/node` endpoints + SSR page). `prom-client` `/metrics`; `Hello` renders one template literal so the SSR HTML carries the greeting contiguously. Same quad-lane discovery + baseline note as the Node batch — recorded under react (nextjs → nextjs lane).)*

Build order: **FastAPI is the reference** (matches the estate; establishes the contract + Dockerfile +
Job + onboarding-decl + hello-retirement pattern end-to-end). Then the rest roll out per-language in
batches, each conforming to the locked contract.

## Definition of Done (per golden path + the system)

Per path: lane-runs (test + selfcheck + coverage) · buildkit image · ephemeral Job exits 0 · onboarding
declaration template present · hello retired (once the language is covered). System: `golden-paths.md`
(this) + a flow diagram + a demo (the CLI/Job walkthrough RUN) + the scaffolder + backlog/Linear.
