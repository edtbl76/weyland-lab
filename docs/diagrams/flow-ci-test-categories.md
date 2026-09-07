# Flow — CI/CD test-category audit + lanes (B152)

The audit evaluated every test category against every language/service, then built the applicable gaps. See
the matrix [ci-test-categories-audit.md](../concepts/ci-test-categories-audit.md) and demo
[ci-test-categories.md](../demos/ci-test-categories.md). LikeC4 placement is N/A (this deploys nothing); these
two flows capture the non-obvious logic — the per-category decision and the architecture-lane enforcement.

## Per-category decision (applicable? → covered? → gap? → outcome)

```mermaid
flowchart TD
    C[each test category x each language/service] --> A{applicable to real code?}
    A -->|no production code| NA1[N/A — fixtures/no surface: Load, fixture langs]
    A -->|yes| CV{already covered?}
    CV -->|yes| DONE1[COVERED — record the evidence: AOP guard tests, Contract verdict-contract]
    CV -->|no| G{worth building for a solo $0 lab?}
    G -->|high ROI| BUILD[BUILD in-pass: Architecture, Property-based, Fuzz]
    G -->|valuable but heavy| ONDEMAND[BUILD on-demand, not a blocking lane: Mutation]
    G -->|no requirement| NA2[N/A — documented reason: Load]
```

## Architecture lane — enforcement (static, dagster-free)

```mermaid
flowchart LR
    subgraph slim [slim CI lane, no dagster]
        L[datasets_lib pure leaves + _collect] --> IL[import-linter grimp static AST]
        CFG[.importlinter — 2 forbidden contracts] --> IL
    end
    IL -->|no forbidden edge| KEPT[KEPT — contracts hold]
    IL -->|leaf imports dagster or a factory| BROKEN[BROKEN — exit 1, named]
    FIX[planted-violation fixture] --> IL
    KEPT --> T[test_architecture.py — real holds]
    BROKEN --> T2[test_architecture.py — violation breaks by reason]
    V[guardrails/verdict.py x2] --> VG[check-verdict-sync.sh in repo-guards]
    VG -->|identical| OK[exit 0]
    VG -->|drift| D1[exit 1]
    VG -->|missing copy| D2[exit 2 fail-closed]
```

- **Decision flow:** most categories resolved to BUILT (architecture, property-based, fuzz), COVERED (contract, AOP), on-demand (mutation), or documented N/A (load, fixture languages) — every one answered, none deferred.
- **Architecture flow:** import-linter runs by static AST so it needs no dagster runtime — it lives in the slim lane exactly where the leaf boundary matters. The planted fixture proves the contract fails on a real violation; `check-verdict-sync.sh` guards the duplicated wire contract fail-closed (0/1/2).
