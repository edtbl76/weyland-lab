# Flow — DataHub catalog coverage (B158-A): govern the DATA estate by CI

The fourth coverage guard, and the first on the data estate rather than infrastructure. Its siblings prove a
service is SCRAPED / VISUALIZED / ALERTED; this proves every mesh dataset is CATALOGED. See the demo
[datahub-coverage.md](../demos/datahub-coverage.md) and the runbook section in
[observability.md](../runbooks/observability.md#datahub-catalog-coverage--the-guard-b158-follow-up-a-2026-09-05).

## The gap it exists to catch

Data-governance completeness had **no positive signal**: a mesh dataset could exist in Trino and never be
emitted to DataHub, and nothing went red. The B158 audit even caught the `data-mesh-map` product tile
drifting from the emit's real `_PRODUCTS` — by hand, because nothing checked it.

```mermaid
flowchart LR
    A[a new dataset lands in Trino<br/>iceberg.datasets_*.* / iceberg.dbt.mart_*] --> B{emitted to DataHub?}
    B -->|yes| C[cataloged: discoverable, governed]
    B -->|no, silently| D[invisible to governance]
    D --> E[no error · no failed test · no alert]
    E --> F[the catalog quietly lies]
```

## The guard — two planes, a set diff

```mermaid
sequenceDiagram
    participant G as check-datahub-coverage.sh
    participant T as Trino (noauth gateway)
    participant D as DataHub GMS
    G->>T: SELECT tables in datasets_*.* + dbt.mart_*
    T-->>G: REALITY set (the mesh tables that exist)
    G->>D: scrollAcrossEntities(DATASET) — paged
    D-->>G: CATALOGED set (+ total, for a completeness check)
    Note over G: reduce each URN to its last two dotted segments,<br/>so iceberg,dbt.mart_x and trino,iceberg.dbt.mart_x both match
    G->>G: REALITY − CATALOGED
    alt every table catalogued
        G-->>G: exit 0 — OK, N/N
    else a table in Trino but not DataHub
        G-->>G: exit 1 — DRIFT, names it
    end
```

## Fail closed — the rule that makes it trustworthy

An absent result must never read as success. The empty-either-side and incomplete-scroll paths are exit 2
(could-not-run), never a clean pass and never "everything is drift".

```mermaid
flowchart TD
    S[run] --> R{REALITY set empty?}
    R -->|yes: Trino read failed| X2a[exit 2 — refuse to grade]
    R -->|no| C{CATALOGED set empty<br/>while REALITY non-empty?}
    C -->|yes: GMS down / no token| X2b[exit 2 — not 'all uncatalogued']
    C -->|no| P{scroll fetched all `total`?}
    P -->|no: partial page| X2c[exit 2 — partial coverage refused]
    P -->|yes| V{any table uncatalogued?}
    V -->|yes| X1[exit 1 — drift]
    V -->|no| X0[exit 0 — OK]
```

Two live-only bugs (invisible to the small bats fixtures) were found + fixed by running it: Trino's
`nextUri` returned on its own in-cluster host (re-pointed to the given endpoint), and `awk | grep -Fxq`
under `set -o pipefail` turned a real match into no-match via SIGPIPE (awk output captured to a variable
first). Live baseline 2026-09-05: **111/111 catalogued, 0 drift**.
