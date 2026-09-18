# Demo — CI/CD test-category audit + new lanes (B152)

B88 built the unit / scan / integration lanes. B152 audited the CI pipeline for the test CATEGORIES those
lanes miss — architecture, contract, AOP, mutation, property-based, fuzz, load — decided which apply, and
built the applicable ones, wired into the existing lanes. Audit + matrix:
[ci-test-categories-audit.md](../concepts/ci-test-categories-audit.md); flow:
[flow-ci-test-categories.md](../diagrams/flow-ci-test-categories.md).

This is repo tooling — there is no UI. The **CLI walkthrough IS the test**, run in the CI's exact images,
and it includes the **negative cases** (each guard shown failing with its exit code — a guard nobody has
watched fail is not a guard).

## CLI walkthrough (RUN 2026-09-06, CI images)

All from `nodes/mother/lab/weyland-platform/services/weyland-dagster/` unless noted.

**1. Architecture (import-linter, static AST — runs dagster-free in the slim lane):**

```
pip install import-linter==2.15
lint-imports
# Analyzed 181 files, 558 dependencies.
# datasets_lib pure leaves + _collect must not import dagster ... KEPT
# datasets_lib pure leaves must not import the factories (leaf < factory) KEPT
# Contracts: 2 kept, 0 broken.
```

Negative case — a planted leaf that imports dagster MUST break the contract (proved by reason, not bare exit):

```
lint-imports --config tests/arch/fixtures/importlinter-violation.ini
# fixture leaf must not import dagster BROKEN  → exit 1
pytest tests/test_architecture.py -q          # 2 passed (real holds + violation breaks)
```

**2. Property-based (hypothesis on the pure leaves):**

```
pytest tests/test_property_based.py -q         # 4 passed
# invariants: domain_job_plan land == transform-exclusion (single-sourced, any land_deps);
#             _collect never yields a check as an asset; collect_checks flattens only *_checks lists
```

**3. Fuzz (hypothesis, the untrusted-HTML parser):**

```
pytest tests/test_fuzz.py -q                   # 2 passed — 250+ adversarial inputs/property + nasty @examples
# edgar_text_parse never crashes, the 8-key chunk contract holds, chunk_id stays sequential,
# metadata is preserved; the run completing proves the greedy chunker terminates
```

**4. Mutation (on-demand — NOT a blocking lane):**

```
scripts/run-mutation.sh
# → mutating weyland_pipeline/assets/_collect.py against tests/test_collect.py tests/test_property_based.py
# 5/5  🎉 5  🙁 0   — every injected bug is caught; a 🙁 survivor would name a coverage gap
```

**5. verdict.py wire-contract guard (repo-guards, fail-closed):**

```
bash scripts/check-verdict-sync.sh
# OK — guardrails/verdict.py is byte-identical across weyland-guard and weyland-tool-server (30 lines).  → exit 0
```

Negative cases (`scripts/tests/verdict-sync.bats`, RUN): drift between the two copies → **exit 1** ("DRIFT" + diff);
a missing copy → **exit 2** ("CANNOT RUN") — never a false pass.

**6. Contract + AOP — covered by existing tests (evaluated, no new lane):**

```
pytest weyland-guard/tests/test_verdict_contract.py -q   # guard↔tool-server Hook/Decision wire contract
pytest weyland-guard/tests/test_pipeline.py tests/test_policy.py tests/test_metrics.py -q  # cross-cutting hooks/gate/metrics
```

**Whole suite, green together (CI images):** python lane **120 passed**; `bats scripts/tests/` **406 passed**;
`shellcheck --severity=warning scripts/*.sh` **0**; `.woodpecker.yml` parses. The arch/property/fuzz tests ride
the existing python lane (import-linter + hypothesis are in `requirements-test.txt`); `check-verdict-sync.sh`
runs in the `repo-guards` step.

## Extension — Java ArchUnit + upper-layering + framework-free contracts (RUN 2026-09-18, CI images)

The 2026-09-06 pass shipped only the Python `import-linter` architecture lane; the **Java ArchUnit** the audit
named "BUILD now" (matrix row 1) was completed here, plus two Python extensions. Each is self-checking (a planted
violation trips the rule by reason), verified through the full `test-python` + `test-java` lanes + ratchets (no
regression) with the SonarQube gate green — pipeline **153** `success`.

**7. Architecture — Flink Java ArchUnit (`mvn test`, existing test-java lane):**

```
# from k8s/flink/health-job and k8s/flink/sql-runner (maven:3.9-eclipse-temurin-21)
mvn -B test
# Running lab.weyland.flink.ArchitectureTest — Tests run: 3, Failures: 0
#   productionCodeDoesNotAccessStandardStreams · productionClassesResideInTheModulePackage
#   ruleCatchesAPlantedStandardStreamAccess (the negative case)
# BUILD SUCCESS  (health-job + sql-runner)
```

Negative case — the planted `StdoutOffender` (writes `System.out`) MUST trip
`NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS`, asserted by the offending class name, not a bare boolean;
`ruleCatchesAPlantedStandardStreamAccess` is green precisely because the rule flags it. (`SqlRunner`'s own
`System.out.println` was moved to slf4j `LOG.info` so the production rule holds.)

**8. Architecture — dagster upper-layering (2 new `.importlinter` contracts):**

```
# weyland-dagster/ (python:3.12-slim)
lint-imports    # Contracts: 4 kept, 0 broken  (added: resources-are-independent, leaves-are-resource-free)
pytest tests/test_architecture.py -q            # 2 passed
```

Negative case — the extended planted fixture breaks all three forbidden contracts at once:

```
lint-imports --config tests/arch/fixtures/importlinter-violation.ini
# leaf→dagster, leaf→resource, resource.thing→asset all BROKEN  → "3 broken", exit 1
```

**9. Architecture — guard + tool-server framework-free (`import-linter`):**

```
# weyland-guard/ and weyland-tool-server/ (python:3.12-slim)
lint-imports    # guardrails-are-framework-free KEPT — Contracts: 1 kept, 0 broken
pytest tests/test_architecture.py -q            # 2 passed (each service)
```

Negative case — a planted guardrail importing fastapi breaks the contract:

```
lint-imports --config tests/arch/fixtures/importlinter-violation.ini
# fixture guardrail must not import the web framework BROKEN  → "1 broken", exit 1
```

**CI-validated end-to-end:** pipeline **153** `success` — `test-python` (14 projects + fixture, ratchet
held/improved across 15), `test-java` (4 projects + fixture, `sql-runner` ratcheted 33.3→34.7%), SonarQube
`sonar-gate` **PASSED**. The deliberately-bad fixtures (`**/StdoutOffender.java`, `**/tests/arch/fixtures/**`)
and the intentionally-parallel arch files are `sonar.exclusions` / `sonar.cpd.exclusions`'d so scaffolding does
not register as new violations or duplication.

## UI walkthrough

N/A — repo tooling, no UI surface. Outcomes surface on the existing pattern (Q6): lane pass/fail in Woodpecker CI
like the other B88 lanes; CI/quality outcomes flow to Port / the Code Health dashboard (B63/B106).

## Teardown

Read-only. The tests and guards write only local, gitignored caches (`.pytest_cache/`, `.mutmut-cache/`,
`.hypothesis/`, `.import_linter_cache/`, maven `target/`); nothing is deployed or persisted. `run-mutation.sh` is
on-demand and mutates a working copy in memory, restoring the source.
