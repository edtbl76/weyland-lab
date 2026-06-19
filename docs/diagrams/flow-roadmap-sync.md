# Flow: Roadmap-Sync → Hermes Kanban (B27)

Hermes mirrors `docs/backlog.md` into its Kanban as a **one-way, read-only** board (`weyland-roadmap`). Every
card is parked at `--initial-status blocked` so the dispatcher never actions it (DONE items are marked
complete); the backlog stays the single source of truth and the script **never writes back**. This is distinct
from Hermes' *self-management* board, which the agent does own. The 6h cadence is external (cron/manual) — the
script itself does no scheduling, and it has **no prune step** (items dropped from the backlog are simply skipped,
not deleted).

```mermaid
sequenceDiagram
    participant Cron as Hermes cron (6h, external)
    participant RS as roadmap-sync.py
    participant GH as GitHub raw (raw.githubusercontent.com/.../docs/backlog.md)
    participant CLI as hermes kanban CLI
    participant KB as Kanban board (weyland-roadmap)
    participant U as Operator (Hermes dashboard)
    Cron->>RS: run roadmap-sync
    RS->>GH: GET raw docs/backlog.md
    RS->>RS: parse items + status markers
    RS->>CLI: create/upsert cards (--initial-status blocked, DONE marked complete)
    CLI->>KB: persist
    U->>KB: view weyland-roadmap board
    Note over RS,KB: mirror only -- no write-back to backlog.md, no prune of removed items
```
