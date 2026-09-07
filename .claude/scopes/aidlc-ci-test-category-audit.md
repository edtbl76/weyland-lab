---
name: ci-test-category-audit
depth: Practical
keywords: []
description: Audit CI/CD for absent test categories (AOP, contract, architecture) across the real-code stack and build the gaps worth adding, wired into the existing B88 lanes
skeleton: off
---

# ci-test-category-audit scope

A composed, focused scope (ARS 37/100, Focused band) for B152 / EMA-209:
audit the CI/CD pipeline (`run-lang-tests.sh`, `run-lang-scan.sh`,
`.woodpecker.yml`) for whole categories of testing that are absent —
AOP/cross-cutting, consumer/provider contract (Pact-style), and
architecture (ArchUnit-style) — decide which apply to the lab's real-code
stack (Python: weyland-dagster/guard/tool-server/scripts; Java: 2 Flink
modules), and close the gaps worth adding, wired into the existing CI lanes
the way B88 added the test/scan/integration tiers.

Not inferable: `keywords: []`. Resolve with `--scope ci-test-category-audit`.

## No deferral

This is scoped as **no-deferral**: the workflow resolves and builds all three
categories (architecture, contract, AOP) in-pass. Nothing is punted to a
separate backlog item. Architecture tests (import-linter / pytest-archon for
Python, ArchUnit for Java) are static and are the highest-ROI category given
real currently-unenforced boundaries (the dagster-free leaf-module
absolute-imports rule, the datasets_lib factory layering, the byte-for-byte
duplicated `guardrails/verdict.py` across weyland-guard and weyland-tool-server,
and "no dagster import in the slim test lane"). Contract testing's data seams
are already done (B157/ODCS) and API seams belong to B155, leaving the optional
1-2 RPC seams — the workflow decides at domain-design whether to build them and,
if a persistent stood-up test provider is warranted, **arms the deployment
overlay live via in-flight recompose** rather than deferring to a follow-up.

## Why requirements-analysis executes

Each architecture rule is pinned as a formal pass/fail requirement **with its
expected-violation fixture BEFORE design**. This is direct insurance against
this lab's most-repeated failure mode: tests that pass against a missing
implementation — the SMOKE gate green on exit 127, stubbed tests confirming only
the author's assumption, the no-dagster slim-lane autodiscovery bug. A rule is
not "enforced" until a fixture proves it fails on a real violation; that
pass/fail criterion is authored as a requirement, then designed, built, and
verified fail-closed at build-and-test.

## Why these stages, why skip those

Ten stages execute: initialization; `intent-capture` (the going-in category
triage and the contract-in/out decision); `reverse-engineering` (the audit —
maps current lanes AND the existing B88 integration tier that black-boxes live
in-cluster services); `requirements-analysis` (arch rules as pass/fail
requirements + fixtures); `domain-design` (which gaps to close, tool/rule/lane
design, and the contract provider-strategy decision that arms/disarms the
deployment overlay); `code-generation` and `build-and-test` (implement and prove
fail-closed, bats for shell gate logic); and `ci-pipeline` (wire the new lanes
into Woodpecker like B88).

Skipped: market-research, team-formation, mockups (internal CI tooling, solo
lab, no UI); feasibility, functional-design, nfr-requirements/design,
infrastructure-design (standard documented tools over the established B88
pattern — folded into domain-design and code-generation); user-stories,
units-generation, contract-design, delivery-planning (no personas, few pieces
with light coupling, no formal inter-unit contract). The deployment/operation
phase is SKIP because architecture tests are static and contract/integration
tests ride already-deployed services + ephemeral in-lane containers (the B88
integration pattern). The narrower contract-with-persistent-provider case —
which pulls in infrastructure-design, nfr-design, deployment-pipeline,
environment-provisioning, and deployment-execution — stays an in-flight
recompose armed at domain-design, not folded in now. Skips the walking-skeleton
ceremony.

## Membership

Initialization, intent-capture, reverse-engineering, requirements-analysis,
domain-design, code-generation, build-and-test, and ci-pipeline execute; the
rest is SKIP.
