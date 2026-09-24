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

    G->>L: { team(EMA) { issues { identifier state{type name} project{name} priority } } }
    L-->>G: HTTP status checked explicitly — a 401 must not read as "no issues"
    Note over G: match on state.TYPE, never the display name —<br/>this workspace has two `started` states

    G->>L: { initiatives { name projects { name } } }
    L-->>G: initiative to project map, 50x50 page, hasNextPage is fatal
    Note over G: weyland scope = projects of Lab & Systems<br/>missing or empty scope initiative -> exit 2

    loop every ref
        G->>G: A backlog=done AND state not terminal -> DRIFT<br/>C priority tag != Linear field -> PRIORITY DRIFT
    end
    loop every issue
        G->>G: B open AND no project -> ORPHAN<br/>D missing, E/F orphan-num / unnumbered IF project in scope
    end

    G->>L: { team(EMA) { projects { name } } }
    Note over G: a SEPARATE query — an empty project has 0 issues,<br/>so parity cannot come from the issue snapshot
    G->>B: read repos.yaml active-repo linear_project map
    loop every ACTIVE repo
        G->>G: G no linear_project, or a name not in live projects -> PARITY GAP
    end
    loop every LIVE project
        G->>G: H in zero initiatives, or in two or more -> INITIATIVE GAP
    end
```

## The checks

Eight now (A–H); the highest-signal are drawn — status (A), project (B), repo↔project parity (G) and
project↔initiative membership (H). Priority drift (C), missing-from-Linear (D), orphan-in-Linear (E) and
unnumbered (F) run the same way and are listed in the guard header. E and F apply only inside the
**weyland scope** — the projects of the `Lab & Systems` initiative, read live (2026-09-24; it replaced a
hard-coded "other products" denylist that went stale with every new project).

```mermaid
flowchart TD
    A["A: for each backlog ref"] --> B{"backlog says DONE?"}
    B -- no --> OK1["fine — open in both"]
    B -- yes --> C{"Linear state.type<br/>terminal?"}
    C -- yes --> OK2["reconciled"]
    C -- no --> D["<b>DRIFT</b> — exit 1"]

    E["B: for each OPEN issue"] --> F{"has a project?"}
    F -- yes --> OK3["findable"]
    F -- no --> G["<b>ORPHAN</b> — exit 1<br/>invisible to every filtered view"]

    J["G: for each ACTIVE repo in repos.yaml"] --> K{"linear_project set<br/>AND names a live project?"}
    K -- yes --> OK4["mapped 1:1"]
    K -- no --> L2["<b>PARITY GAP</b> — exit 1<br/>no project, or a stale/renamed name"]

    M["H: for each LIVE project"] --> N{"in exactly ONE<br/>initiative?"}
    N -- yes --> OK5["scoped"]
    N -- no --> N2["<b>INITIATIVE GAP</b> — exit 1<br/>in no one's scope, or ambiguous"]

    H["cannot read backlog / no API key / HTTP != 200 /<br/>empty snapshot / zero projects / unreadable repos.yaml /<br/>scope initiative missing or empty"] --> I["<b>exit 2</b><br/>guard broken, NOT a clean estate"]

    style D fill:#ffdddd,stroke:#cc0000
    style G fill:#ffdddd,stroke:#cc0000
    style L2 fill:#ffdddd,stroke:#cc0000
    style N2 fill:#ffdddd,stroke:#cc0000
    style I fill:#ffe8cc,stroke:#cc8800
```

**One-way on purpose.** DONE implies closed; the converse is not asserted — an issue closed in Linear
while the backlog entry is still open is a normal mid-flight state, not drift.

**Exit 1 and exit 2 are never conflated.** A missing `LINEAR_API_KEY` must not read as a clean backlog.
That substitution — absence standing for success — is the defect this whole family of guards exists for.

**The invariant:** every backlog item claiming DONE is closed in the system that owns status, every open
issue is reachable from a project filter, and every active repo in `repos.yaml` maps 1:1 to a live Linear
project (check G, 2026-09-23), and every live project sits in exactly one initiative (check H, 2026-09-24).
None of it is assertable by hand any more.
