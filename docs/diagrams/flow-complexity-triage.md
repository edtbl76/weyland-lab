# Flow: complexity triage (B162)

How `scripts/lib/complexity_triage.py` reads a function: length only NOMINATES; structure and the
codebase-relative outlier decide; the inverse smell (shallow / over-split) is caught in the other direction.
Concept: [concepts/reading-complexity.md](../concepts/reading-complexity.md) · runbook:
[runbooks/complexity-triage.md](../runbooks/complexity-triage.md).

```mermaid
flowchart TD
    SRC[Real-code files<br/>Python + Java + more] --> LZ[lizard<br/>LOC + cyclomatic + params]
    SRC --> TS[tree-sitter<br/>true max-nesting<br/>delegation + decorators]

    LZ --> POP[Per-language population<br/>mean + stdev per nloc/ccn]
    LZ --> S1{Stage 1 nominate<br/>loc over length_warn?}
    TS --> S1

    S1 -->|no| SKIP[Not a candidate<br/>silent]
    S1 -->|yes| S2{Stage 2 structure<br/>density or nesting high?}

    S2 -->|dense or deep pyramid| TANGLED[TANGLED<br/>stop and fix]
    S2 -->|clean| S3{Stage 3 codebase-relative<br/>z-score outlier?}
    POP --> S3

    S3 -->|unusual for this codebase| REVIEW[OUTLIER_REVIEW<br/>a human glance]
    S3 -->|typical + low density| DEEP[DEEP<br/>acceptable]

    TS --> INV{Inverse smell<br/>N siblings delegate<br/>to the same target?}
    INV -->|yes, non-framework| SHALLOW[SHALLOW<br/>over-split, stop and fix]

    TANGLED --> OUT[Graded report]
    SHALLOW --> OUT
    REVIEW --> OUT
    DEEP --> OUT
    OUT --> POST{Posture}
    POST -->|advisory default| A0[exit 0, print]
    POST -->|--gate| A1[TANGLED/SHALLOW exit 1]
```

Advisory by default (like Graphify's Pillar-8 wiring); `--gate` blocks on `TANGLED`/`SHALLOW` once the thresholds
are trusted. Every threshold is a knob in `scripts/complexity-triage.json`.
