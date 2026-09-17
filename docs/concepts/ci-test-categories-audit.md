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
| 2 | **Contract** (consumer/provider) | ✅ top seam covered | — | N/A | ✅ **COVERED** | **No new lane** — top seam + data + live all covered |
| 3 | **AOP / cross-cutting** | ✅ applicable (guard pipeline) | — | N/A | ✅ **COVERED** | **No build** — already asserted; infra aspects N/A |
| 4 | **Mutation** | ✅ applicable (pure leaves) | ✅ applicable | N/A | ✅ **on-demand harness** | **BUILT** — `scripts/run-mutation.sh` (opt-in, not a lane); `_collect` 5/5 killed |
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

### 2. Contract — COVERED (evaluated, proportionate)
On inspection the highest-value RPC seam is **already** a consumer/provider contract: `weyland-guard/tests/test_verdict_contract.py` pins the `Hook`/`Decision` wire shape between guard (provider) and tool-server (HTTP client) — `Hook` values are the URL routes, `Decision` values are what the client parses — and it has been verified to fail on drift. This B152 pass reinforced it at the byte level with `scripts/check-verdict-sync.sh` (repo-guards). The other contract surfaces are covered too: **data** contracts by ODCS (**B157**), **API lifecycle** by **B155**, and the live services by the B88 **integration tier** (`test-integration-guard`, `test-integration-datahub` black-box the deployed seams). The only net-new would be a second offline seam (e.g. tool-server `/context/search` response shape), which has no test harness today and duplicates the integration tier's live coverage — disproportionate for a solo $0 lab. Verdict: covered; no new contract lane. (If a future seam grows a formal schema, add its shape assertion then.)

### 3. AOP / cross-cutting — COVERED (evaluated, no build needed)
On inspection the app-level cross-cutting behaviour is **already asserted** in weyland-guard: `test_pipeline.py`
proves the pipeline's hook/mode gating (SHADOW records-but-doesn't-block, BLOCK returns block, the actor is
threaded into the record across hooks); `test_policy.py` proves the enforcing act gate (blocks on no-actor /
unknown-actor / disallowed-tool, plus the rate limiter); `test_metrics.py` proves the metrics aspect fires.
That IS the AOP surface here. The remaining cross-cutting concerns are infrastructure — Istio mTLS and
Keycloak forward-auth — which are N/A at the unit level (enforced by mesh/ingress config and exercised by the
B88 integration tier), not app decorators. Verdict: no new AOP lane; the category is covered, and this row is
the audit's evidence that it was checked rather than assumed.

### 4. Mutation — BUILT as an on-demand harness (not a standing lane)
Mutation testing (mutmut) checks test *quality* by injecting bugs; a standing CI lane is disproportionate for a $0 lab (slow/expensive). Delivered as **`scripts/run-mutation.sh`** — a targeted, opt-in runner over the highest-value pure leaves, defaulting to `_collect` (the autodiscovery collector whose bug caused the outage). Proven 2026-09-06: `_collect` scored **5/5 mutants killed** (its example + property tests catch every mutation). Run it after changing a leaf or its tests; a surviving mutant names a coverage gap. Not wired into the blocking lane by design.

### 5. Property-based — BUILD now (high-ROI)
The pure transform leaves have clear invariants (idempotence, no-null-leak, round-trip, "empty in → empty out fail-closed"). **hypothesis** (Python) property tests on `_collect`, the `*_parse` leaves, `market_parse`, `edgar_text_parse`, `land_core`. High value, cheap, runs in the existing fast lane.

### 6. Fuzz — BUILD narrow
The real fuzz target is the untrusted-input parser: `edgar_text_parse` (SEC 10-K HTML). A small **atheris** (Python) harness, or fold the malformed-input cases into the property-based suite. Low priority; narrow scope.

### 7. Load — N/A (documented, not deferred)
No performance/scale NFR exists; mother is capacity-bound ($0 LAN, no swap). Load-testing the services would harm the shared node for no requirement. The existing observability (OTel latency, ServiceMonitor) covers steady-state. Honest verdict: **not applicable for this lab** — recorded here so it's an answered question, not a silent omission.

## Build status (all seven categories resolved in-pass — no deferrals)

1. **Architecture — DONE (Python), EXTENDED 2026-09-17 (see the addendum below).** `.importlinter` (2 forbidden contracts: leaves-are-dagster-free + leaf<factory), run by static AST in the slim lane; `tests/test_architecture.py` (real holds + a planted violation breaks by reason); `scripts/check-verdict-sync.sh` + `verdict-sync.bats` (the duplicated-verdict wire contract), wired into `repo-guards`. **NOTE:** the original pass shipped only the Python `import-linter` half; the Java ArchUnit this doc named as "applicable — BUILD now" (matrix row 1) was completed in the 2026-09-17 addendum, along with two extensions.
2. **Property-based — DONE.** `tests/test_property_based.py` (hypothesis) on the pure leaves — `domain_job_plan`'s single-sourced split invariant + `_collect`'s disjointness/flatten. Rides the python lane.
3. **Contract — COVERED (no new lane).** The top RPC seam (guard↔tool-server verdict wire) is `test_verdict_contract.py`, reinforced by `check-verdict-sync.sh`; data by ODCS (B157), API by B155, live by the integration tier. A second offline seam is disproportionate (see §2 above).
4. **AOP — COVERED (no new lane).** `test_pipeline.py` / `test_policy.py` / `test_metrics.py` already assert the guard's hook/mode gating, enforcing act gate, and metrics aspect; infra aspects (Istio mTLS, forward-auth) are N/A at unit level.
5. **Fuzz — DONE.** `tests/test_fuzz.py` (hypothesis) fuzzes `edgar_text_parse` (the untrusted-HTML parser) — never crashes, contract holds, chunker terminates.
6. **Mutation — DONE (on-demand).** `scripts/run-mutation.sh` (opt-in, not a blocking lane); `_collect` proven 5/5 mutants killed.
7. **Load — N/A (documented).** No perf/scale NFR; capacity-bound $0 LAN node; steady-state covered by existing observability.
8. **Fixture languages — evaluated → N/A now, pattern documented.** Go/Rust/TS/JS/React/Next carry only B88 hello-world fixtures with no modules/seams, so architecture and property enforcement would test nothing today. The per-language tools are named (dependency-cruiser TS/JS, go-arch-lint Go, cargo-modules/clippy Rust; the matrix rows above) so the pattern activates the moment real production code lands in any of them — enforcing on empty fixtures now would be a control that measures nothing.

Reporting reuses the existing pattern (Q6): lanes report pass/fail in Woodpecker like the B88 lanes; outcomes flow to Port/Code Health; the standard 8-pillar DoD demo (`demos/` + `flow-*`) is the human-readable record.

## Addendum — architecture category extended (2026-09-17)

The original pass (2026-09-06) shipped the Python `import-linter` architecture lane but left the **Java ArchUnit**
that §1 / matrix-row-1 named "applicable — BUILD now" unbuilt, and the Python contracts covered only the
`datasets_lib` leaf<factory boundary. This addendum closes the Java gap and extends the Python contracts. All
three are self-checking (a planted violation is proven to trip the rule by REASON) and were verified in the CI
toolchain images (`python:3.12-slim`, `maven:3.9-eclipse-temurin-21`) through the full `test-python` +
`test-java` lanes and their coverage ratchets — no regression (python held/improved across 15 projects, java
across 5).

1. **Flink Java ArchUnit — BUILT (completes matrix row 1's Java cell).** `com.tngtech.archunit:archunit-junit5`
   (test scope) added to both `health-job` and `sql-runner` poms; `src/test/java/lab/weyland/flink/ArchitectureTest.java`
   in each asserts **no access to standard streams** (a streaming operator must log via slf4j, never `System.out`
   — a keyed-operator `println` floods TaskManager stdout and costs throughput) + package residence, and a
   planted `StdoutOffender` fixture proves the rule trips. ArchUnit reads bytecode statically, so the tests run
   in the existing `test-java` lane (`mvn test`) with no new CI step. **Production fix:** `SqlRunner`'s two
   `System.out.println` logging lines were converted to slf4j `LOG.info` so the rule holds (and now guards
   against a stdout regression); `slf4j-api` added `provided` (the Flink dist supplies the binding at runtime).

2. **dagster upper-layering — 2 contracts added** to `weyland-dagster/.importlinter`: `resources-are-independent`
   (the infra resource clients must not import the pipeline layers assets/schedules/sensors/definitions — they
   are composed by `definitions.py`, never the reverse) and `leaves-are-resource-free` (the pure leaves must not
   import the dagster resource clients — only the `loaders` factory bridges leaf→resource). The planted-violation
   fixture was extended (a package-shaped `resource` submodule) to prove both, and that package-level
   `source_modules` covers descendants.

3. **guard / tool-server framework-free contracts — NEW `.importlinter` + `tests/test_architecture.py`** in both
   services (import-linter added to each `requirements-test.txt`): `guardrails-are-framework-free` forbids the
   guardrail decision logic (guard's policy + validators; the shared `verdict.py` in both) from importing
   fastapi/starlette — so the policy layer stays unit-testable without the web framework and a framework import
   can never propagate through the byte-shared `verdict.py` to every consumer. `app.py`/`main.py` remain the only
   HTTP-wiring layer. A planted fastapi-importing fixture proves each contract trips. This complements (does not
   duplicate) B152's `check-verdict-sync.sh`, which guards the verdict byte-identity rather than its imports.

These ride the existing lanes (no new `.woodpecker.yml` steps): the Python contracts run as `tests/test_architecture.py`
in `test-python`; the Java rules as JUnit tests in `test-java`.
