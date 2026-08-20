---
id: ci-cd
tags: [methodology, deployment, developer-experience, backend]
surfaces-at: [application-design, infrastructure-design]
related: [containers, infrastructure-as-code, shift-left-testing, trunk-based-development, blue-green-deployment, feature-flags]
complexity: intermediate
---

# CI/CD

## What It Is
Continuous Integration (CI) and Continuous Delivery/Deployment (CD) — the practice of automatically building, testing, and deploying code changes on every commit. CI catches integration failures early by building and running tests automatically. CD extends this by automatically deploying validated changes to staging or production. Together they reduce the risk and batch size of deployments, enable rapid iteration, and create a fast feedback loop from code commit to running software.

## When to Apply
- Every software project — CI/CD is table stakes for modern engineering
- Before the team grows — CI/CD is harder to retrofit than to establish from the start
- When deployment frequency is too low or deployment risk is too high

## Key Concepts
- **Continuous Integration**: Every commit to a shared branch triggers an automated pipeline: build, lint, test. Failures are surfaced immediately. The goal is that the main branch is always in a releasable state
- **Continuous Delivery**: Every passing build produces a deployable artifact. Deployment to production is triggered manually — a human decides when to release. Appropriate when production deployments require coordination or approval
- **Continuous Deployment**: Every passing build is automatically deployed to production without human intervention. Requires high test coverage and confidence, feature flags for in-progress work, and robust rollback capability
- **Pipeline Stages**: Typical pipeline: commit → build → unit tests → integration tests → security scan → artifact publish → deploy to staging → smoke tests → deploy to production
- **Fast Feedback**: CI pipelines should complete in under 10 minutes for unit tests. Slow pipelines are ignored or bypassed. Parallelize test suites; run expensive tests only on the main branch
- **Artifact Immutability**: Build once, deploy many times. The same artifact (container image, binary) deployed to staging is the same one deployed to production — no rebuilding at deploy time
- **Trunk-Based Development**: Short-lived feature branches merged frequently to main. Reduces merge conflicts and integration risk. Works best with feature flags to hide incomplete work
- **Pipeline as Code**: Pipeline definitions live in version control alongside the application code — Jenkinsfile, GitHub Actions YAML, GitLab CI YAML, CircleCI config. Changes to the pipeline are reviewed and versioned like any other code
- **Common Tools**: GitHub Actions, GitLab CI, CircleCI, Jenkins, Buildkite, ArgoCD (Kubernetes GitOps)

## In Practice
Method uses GitHub Actions for CI (build, test, security scan, container image push) and ArgoCD for CD (GitOps deployment to Kubernetes). Unit and integration tests run in parallel. Container images are tagged with git SHA and pushed to ECR. Production deployments require a manual promotion step from staging.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — CI/CD**: Build once, deploy the same artifact everywhere — never rebuild for each environment. Keep CI pipelines under 10 minutes for the core test suite; slow pipelines breed bypass habits. Store pipeline definitions as code in the repository. Use feature flags to enable continuous deployment without exposing incomplete features. Trunk-based development with short-lived branches reduces merge conflicts and keeps the main branch deployable. Treat a failing CI pipeline as a production incident — fix it before continuing feature work. → `engineering-knowledge-repository/ci-cd.md`

## Related Entries
- [Containers](containers.md) — container images are the primary artifact built and pushed by CI/CD pipelines
- [Infrastructure as Code](infrastructure-as-code.md) — IaC changes are deployed through CI/CD pipelines
- [Shift-Left Testing](shift-left-testing.md) — CI/CD enables shift-left by running tests automatically on every commit
- [Trunk-Based Development](trunk-based-development.md) — trunk-based development is the branching strategy that maximizes CI/CD effectiveness
- [Blue-Green Deployment](blue-green-deployment.md) — CD pipelines implement blue-green, canary, and rolling deployment strategies
- [Feature Flags](feature-flags.md) — feature flags enable continuous deployment by decoupling code deployment from feature release
