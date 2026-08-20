---
id: continuous-integration
tags: [methodology, deployment, testing]
surfaces-at: [nfr-requirements, code-generation]
related: [trunk-based-development, continuous-delivery, test-pyramid, feature-flags]
complexity: foundational
---

# Continuous Integration (CI)

## What It Is
A development practice where all developers integrate their code changes into a shared branch frequently — at least daily. Every integration triggers an automated build and test run. The goal: catch integration defects immediately rather than letting them accumulate. CI is not a tool (Jenkins, GitHub Actions, CircleCI) — it's the practice of frequent, automated integration.

## When to Apply
- All software development teams — CI is a foundational engineering practice, not an optional advanced technique
- Before adopting Continuous Delivery — CI is the prerequisite
- When integration problems are causing late-stage test failures or painful merges
- When the team lacks confidence that the codebase is always in a releasable state

## When Not to Apply
- CI is always applicable. What varies is depth: a solo script project may need a lighter pipeline than an enterprise microservices system.

## Key Concepts
- **The CI Build**: The automated sequence triggered on every commit — compile, unit test, integration test, lint, security scan
- **Fast Feedback**: The CI build should complete in under 10 minutes — developers wait for feedback; slow pipelines lead to batching
- **Green Build Culture**: The team treats a failing build as the highest priority — no one moves on until the build is green
- **Pipeline as Code**: CI configuration is version-controlled alongside the code — `Jenkinsfile`, `.github/workflows/`, `.gitlab-ci.yml`
- **Test Pyramid in CI**: Unit tests run on every commit; slower integration and E2E tests may run on merge to main or on a schedule
- **Artifacts**: CI produces versioned, immutable build artifacts (container images, JAR files) — the same artifact that passed tests is what gets deployed
- **CI ≠ Build Server**: Many teams have a build server but don't practice CI — they still batch work on long branches. True CI requires frequent integration to trunk.

## In Practice
CI is Method's baseline engineering requirement on all engagements. The pipeline setup (GitHub Actions, CircleCI, Jenkins) is established in Iteration 0 before any feature work. The key discipline is green build culture — every failing build gets fixed immediately, not queued. Pipeline speed is a first-class concern — a 30-minute build kills the feedback loop.

## Engineering Knowledge
💡 **Engineering Knowledge — Continuous Integration**: Integrate to the shared branch every day; automated tests run on every commit. CI is not a build server — it's the practice of frequent integration. The build must stay green: a failing build is the team's highest priority until resolved. Keep pipeline time under 10 minutes — slow builds get ignored. This is the foundation that Continuous Delivery is built on. → `engineering-knowledge-repository/deployment/continuous-integration.md`

## Related Entries
- [Trunk-Based Development](../methodologies/trunk-based-development.md) — the branching strategy that makes CI real
- [Continuous Delivery](continuous-delivery.md) — CI is the prerequisite for CD
- [Test Pyramid](../testing/test-pyramid.md) — the test strategy that enables fast CI pipelines
