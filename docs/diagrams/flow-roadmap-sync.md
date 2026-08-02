# Flow: Roadmap Sync — `docs/backlog.md` ↔ Linear (EMA)

Roadmap and issues live in **Linear** (team `emangini` / **EMA**), but the **committed `docs/backlog.md`** (B-numbered,
in git) is the **single source of truth** for scope. The two are reconciled at the **end of a work batch**: `backlog.md`
drives *what exists and what's planned*, Linear tracks *status*. There is **no automated write-back** — the sync is a
manual / agent step.

```mermaid
sequenceDiagram
    participant Dev as Maintainer / agent
    participant BL as docs/backlog.md (committed source of truth, B-numbered)
    participant LN as Linear (team emangini / EMA)
    Note over BL: scope lives here — what exists, what's planned
    Dev->>BL: add / update B-items as work is scoped
    Note over Dev,LN: at the end of a work batch
    Dev->>LN: reconcile issue status to match completed B-items
    LN-->>Dev: board reflects current status
    Note over BL,LN: backlog.md = source (scope) · Linear = status · no automated write-back
```

> **Owner review:** this diagram captures the current *mechanism* (backlog.md = source, Linear = status, synced
> end-of-batch). If a scripted or scheduled sync exists, wire its exact trigger/cadence in here.
