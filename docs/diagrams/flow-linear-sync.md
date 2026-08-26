# Flow — DoD Pillar 5 reconciliation (backlog ↔ Linear)

Why the one pillar without a checker was the one that failed, and what checks it now.
Sequence + decision matrix (Mermaid); the gate itself is `docs/definition-of-done.md` § 5.

## The gap it closes

```mermaid
flowchart LR
    subgraph BEFORE["Before 2026-08-26"]
      P1["Pillar 1 docs"] --> C1["check-doc-counts.sh"]
      P2["Pillar 2 diagrams"] --> C2["check-mermaid.sh"]
      P3["Pillar 3 demos"] --> C3["human eyes-on"]
      P6["Pillar 6 ops"] --> C6["check-cron-freshness-budgets.sh"]
      P7["Pillar 7 scan"] --> C7["shellcheck + bats"]
      P5["<b>Pillar 5 tracking</b>"] --> C5["<b>nothing</b>"]
    end
    C5 --> R["the tick WAS the work<br/>so it recorded INTENT,<br/>never outcome"]

    style P5 fill:#ffdddd,stroke:#cc0000
    style C5 fill:#ffdddd,stroke:#cc0000
    style R fill:#fff4dd,stroke:#cc8800
```

**It failed the day it was noticed.** The B148 close-out recorded *"5 — Linear EMA-207, backlog flipped"*
while **no Linear call had been made at all**; the issue sat in `Backlog`. Checking then found **B143**
had been open for two days after shipping, and **three** open issues had no project.

## What runs now

```mermaid
sequenceDiagram
    autonumber
    participant G as check-linear-sync.sh
    participant B as docs/backlog.md
    participant L as api.linear.app/graphql

    G->>B: scan BOTH regions
    Note over B: 1. ordered priority list — `1. **B46** … [Linear EMA-35]`<br/>2. `### B<n>` detail sections — `Linear: EMA-207`<br/>skip `(original entry)` collapsed duplicates
    B-->>G: 26 refs as `<B-num> <EMA-id> <done|open>`
    Note over G: status = FIRST status-or-priority token on the line.<br/>A bare `\bDONE\b` search reads a 1574-char entry's<br/>prose about OTHER items as its own.

    G->>L: { team(EMA) { issues { identifier state{type name} project{name} } } }
    L-->>G: HTTP status checked explicitly — a 401 must not read as "no issues"
    Note over G: match on state.TYPE, never the display name —<br/>this workspace has two `started` states

    loop every ref
        G->>G: backlog=done AND state not terminal -> DRIFT
    end
    loop every OPEN issue
        G->>G: no project -> ORPHAN
    end
```

## The two checks

```mermaid
flowchart TD
    A["for each backlog ref"] --> B{"backlog says DONE?"}
    B -- no --> OK1["fine — open in both"]
    B -- yes --> C{"Linear state.type<br/>terminal?"}
    C -- yes --> OK2["reconciled"]
    C -- no --> D["<b>DRIFT</b> — exit 1"]

    E["for each OPEN issue"] --> F{"has a project?"}
    F -- yes --> OK3["findable"]
    F -- no --> G["<b>ORPHAN</b> — exit 1<br/>invisible to every filtered view"]

    H["cannot read backlog / no API key /<br/>HTTP != 200 / empty snapshot"] --> I["<b>exit 2</b><br/>guard broken, NOT a clean backlog"]

    style D fill:#ffdddd,stroke:#cc0000
    style G fill:#ffdddd,stroke:#cc0000
    style I fill:#ffe8cc,stroke:#cc8800
```

**One-way on purpose.** DONE implies closed; the converse is not asserted — an issue closed in Linear
while the backlog entry is still open is a normal mid-flight state, not drift.

**Exit 1 and exit 2 are never conflated.** A missing `LINEAR_API_KEY` must not read as a clean backlog.
That substitution — absence standing for success — is the defect this whole family of guards exists for.

**The invariant:** every backlog item claiming DONE is closed in the system that owns status, and every
open issue is reachable from a project filter. Neither is assertable by hand any more.
