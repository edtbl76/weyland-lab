# CI/CD Test-Category Audit (B152 / EMA-209)

**Purpose:** identify existing test patterns and gaps across the CI lanes, for **every** test category × **every** language/service, then close the gaps worth closing — wired into the existing lanes the way B88 added test/scan/integration lanes. No category is dropped or sampled; no gap is deferred to a separate item.

Audit method: read the actual lane machinery (`scripts/run-lang-tests.sh`, `scripts/run-lang-scan.sh`, `.woodpecker.yml`) and the real code, not assumptions.

## What exists today (baseline)

| Category | Where | What it does |
|----------|-------|--------------|
| **Unit** | `run-lang-tests.sh` (pytest / mvn / go test / cargo / node --test / jest) + `coverage-ratchet.sh` | Per-language unit suites, discovered by test file → project root; coverage floor ratchet |
| **Static / SAST** | `run-lang-scan.sh` (clippy, cargo-audit/deny, spotbugs, checkstyle, eslint, npm-audit) + the 19-tool `code-scan-suite` (bandit, semgrep, trivy, …) + SonarQube | Lint + security static analysis |
| **Integration** | B88 tier in `.woodpecker.yml` (`test-integration-guard`, `test-integration-datahub`) | Black-box **live in-cluster** services (weyland-guard, DataHub↔Redpanda) |

The seven target categories below have **no tooling at all** today.

## The real-code surface

- **Python (real code):** `weyland-dagster` (the `datasets_lib` factory + pure `*_parse`/`_collect` leaves), `weyland-guard` (guard pipeline + validators), `weyland-tool-server` (RAG + HTTP; shares a byte-duplicated `verdict.py` with guard), `scripts/` (shell + `gen_odcs_contract.py`)
- **Java (real code):** the 2 Flink modules (`health-job`, `sql-runner`)
- **Fixtures only (no production code):** Go, Rust, TypeScript, JavaScript, React, Next.js — B88 hello-world lanes. Per the intent, these are in-scope to **seed the pattern per language**, not to produce findings.

## Finding matrix — category × surface (applicable? / covered? / gap?)

| # | Category | Python real | Java real | Fixture langs | Covered? | Verdict |
|---|----------|-------------|-----------|---------------|----------|---------|
| 1 | **Architecture** (ArchUnit-style) | ✅ applicable — strong | ✅ applicable | seed pattern | ❌ none | **BUILD now** (highest-ROI) |
| 2 | **Contract** (consumer/provider) | ◑ partial (integration tier + ODCS/B157 data contracts) | — | N/A | ◑ partial | **BUILD selectively** (1–2 RPC seams) |
| 3 | **AOP / cross-cutting** | ◑ thin (guard hooks, retry) | — | N/A | ❌ none | **BUILD thin** (guard pipeline hooks) |
| 4 | **Mutation** | ✅ applicable (pure leaves) | ✅ applicable | N/A | ❌ none | **BUILD targeted** (one-shot on critical leaves, not standing CI) |
| 5 | **Property-based** | ✅ applicable — strong (pure leaves) | ◑ possible | seed pattern | ❌ none | **BUILD now** (high-ROI on the transform leaves) |
| 6 | **Fuzz** | ◑ narrow (parsers) | — | N/A | ❌ none | **BUILD narrow** (the HTML/text parser) |
| 7 | **Load** | ✗ not applicable | ✗ | N/A | ❌ none | **N/A — documented** (no perf NFR; capacity-bound $0 LAN node) |

Legend: ✅ applicable · ◑ partial/thin · ✗ not applicable.

## Per-category detail + gap

### 1. Architecture — BUILD now (highest-ROI)
Real, currently-unenforced boundaries, each a live drift risk:
- **dagster-free leaf rule** — `datasets_lib/*_parse.py` + `_collect.py` must use absolute imports only (so `conftest.load_isolated` can test them without the dagster runtime). Enforced today *only* because a test happens to load them — the exact class that let the autodiscovery outage through.
- **datasets_lib layering** — leaf (`*_parse`, `_collect`) → factory (`landers`, `broker`, `loaders`) → assets; a leaf must not import a factory or dagster.
- **verdict.py duplication** — `guardrails/verdict.py` is byte-duplicated across `weyland-guard` and `weyland-tool-server`; nothing keeps them in sync.
- **no-dagster-in-slim-lane** — the fast test lane must not import dagster.

Tooling ($0): **import-linter** or **pytest-archon** (Python), **ArchUnit** (Java). Each rule ships with a passing fixture AND a deliberately-failing fixture, and is proven to FAIL on the real violation (the Q2 coverage metric).

### 2. Contract — BUILD selectively
Data-contract seams are done (**B157/ODCS**); API-lifecycle is **B155**. Net-new = service RPC seams (guard `/guard/*`, tool-server `/context/search`, feast-server, MCP). The integration tier already black-boxes live services. Add consumer/provider contract assertions on the **1–2 highest-value seams** (guard verdict shape; tool-server search response shape) following the existing already-deployed + ephemeral pattern — **not** a Pact broker (over-engineering for a solo $0 lab).

### 3. AOP / cross-cutting — BUILD thin
Most cross-cutting here is infra (Istio mTLS, forward-auth) — N/A at unit level, covered by mesh config + integration. The testable app-level aspects: the **guard pipeline hooks** (does the verdict decorator/interceptor actually fire and block?) and retry/rate-limit logic. Assert those fire; document the infra aspects as N/A.

### 4. Mutation — BUILD targeted (not a standing lane)
Mutation testing (mutmut/cosmic-ray Python, PIT Java) checks test *quality* by injecting bugs. Valuable but slow/expensive — a standing CI lane is disproportionate for a $0 lab. Verdict: a **targeted, opt-in** mutation run on the highest-value pure-logic leaves (the parse/collect functions + guard validators) as a quality check, runnable on demand, not blocking every push.

### 5. Property-based — BUILD now (high-ROI)
The pure transform leaves have clear invariants (idempotence, no-null-leak, round-trip, "empty in → empty out fail-closed"). **hypothesis** (Python) property tests on `_collect`, the `*_parse` leaves, `market_parse`, `edgar_text_parse`, `land_core`. High value, cheap, runs in the existing fast lane.

### 6. Fuzz — BUILD narrow
The real fuzz target is the untrusted-input parser: `edgar_text_parse` (SEC 10-K HTML). A small **atheris** (Python) harness, or fold the malformed-input cases into the property-based suite. Low priority; narrow scope.

### 7. Load — N/A (documented, not deferred)
No performance/scale NFR exists; mother is capacity-bound ($0 LAN, no swap). Load-testing the services would harm the shared node for no requirement. The existing observability (OTel latency, ServiceMonitor) covers steady-state. Honest verdict: **not applicable for this lab** — recorded here so it's an answered question, not a silent omission.

## Bounded build plan (priority order)

1. **Architecture lane** (Python import-linter/pytest-archon + Java ArchUnit) — the 4 boundary rules above, each with pass + deliberately-fail fixtures. Wire into `.woodpecker.yml` like the B88 lanes.
2. **Property-based** — hypothesis suites on the pure leaves, run in the existing python test lane.
3. **Contract** — 1–2 RPC-seam contract assertions in the integration tier.
4. **AOP** — guard-pipeline hook assertions.
5. **Fuzz** — narrow atheris harness on `edgar_text_parse` (or folded into property-based).
6. **Mutation** — targeted opt-in run on the critical leaves (on-demand, not blocking).
7. **Load** — documented N/A (no build).
8. **Fixture languages** — seed a minimal arch-rule config + one property-test example per fixture so the pattern exists when real code lands.

Reporting reuses the existing pattern (Q6): lanes report pass/fail in Woodpecker like the B88 lanes; outcomes flow to Port/Code Health; the standard 8-pillar DoD demo (`demos/` + `flow-*`) is the human-readable record.
