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

## UI walkthrough

N/A — repo tooling, no UI surface. Outcomes surface on the existing pattern (Q6): lane pass/fail in Woodpecker CI
like the other B88 lanes; CI/quality outcomes flow to Port / the Code Health dashboard (B63/B106).

## Teardown

Read-only. The tests and guards write only local, gitignored caches (`.pytest_cache/`, `.mutmut-cache/`); nothing
is deployed or persisted. `run-mutation.sh` is on-demand and mutates a working copy in memory, restoring the source.
