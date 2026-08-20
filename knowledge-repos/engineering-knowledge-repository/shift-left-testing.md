---
id: shift-left-testing
tags: [principle, testing]
surfaces-at: [code-generation, nfr-requirements]
related: [test-doubles, mutation-testing, property-based-testing, continuous-integration, definition-of-done]
complexity: foundational
---

# Shift-Left Testing

## What It Is
The practice of moving testing activities earlier in the development lifecycle — "to the left" on the timeline. Instead of testing after code is written and deployed, shift-left means writing tests before or alongside code (TDD), running automated tests on every commit (CI), and catching defects when they are cheapest to fix — during development, not in production. The core insight: a bug found in code review costs 10x less to fix than one found in production.

## When to Apply
- Always — shift-left is a continuous improvement posture, not a one-time activity
- When establishing engineering practices for a new team or project
- When defect escape rates (bugs reaching production) are high

## Key Concepts
- **Test-Driven Development (TDD)**: Write the test before the implementation — the test defines the specification. Red → Green → Refactor cycle
- **SAST (Static Application Security Testing)**: Automated security analysis run in CI — catches vulnerabilities before code review (SonarQube, Semgrep, Checkmarx)
- **Pre-Commit Hooks**: Run fast checks locally before a commit is created — linting, formatting, secret detection. Catch issues before they hit CI
- **Test Pyramid**: Foundational framework for shift-left: many fast unit tests at the base, fewer integration tests in the middle, few slow E2E tests at the top. Most defects caught at the unit layer
- **Fail Fast**: Tests should fail clearly and quickly on the earliest signal of a problem — don't wait for a downstream test to surface an upstream bug
- **Cost of Defects Curve**: The cost to fix a defect grows exponentially as it moves through development → testing → staging → production. Shift-left is cost reduction
- **Definition of Done as Gate**: Including "tests written and passing" in the DoD enforces shift-left as a team norm

## In Practice
Shift-left in Method engagements means: TDD or test-concurrent development for business logic, pre-commit hooks for linting and secret scanning, unit and integration tests in every PR CI pipeline, and SAST scanning integrated into CI. Definition of Done includes test coverage requirements. No code is done without tests.

## Engineering Knowledge
💡 **Engineering Knowledge — Shift-Left Testing**: Test early, test often, test automatically. The cost of fixing a bug grows exponentially from development to production — catch it in the unit test layer. TDD forces specification before implementation. Pre-commit hooks prevent secrets and linting issues from ever reaching CI. CI runs the test suite on every commit. SAST finds vulnerabilities before code review. The test pyramid: many fast unit tests, fewer integration tests, few E2E tests. → `engineering-knowledge-repository/testing/shift-left-testing.md`

## Related Entries
- [Continuous Integration](../deployment/continuous-integration.md) — CI is the infrastructure for automated shift-left testing
- [Test Doubles](test-doubles.md) — test doubles enable fast, isolated unit tests in the shift-left model
- [Definition of Done](../team-practices/definition-of-done.md) — DoD encodes shift-left as a team quality gate
- [Mutation Testing](mutation-testing.md) — mutation testing verifies that shift-left tests are meaningful
