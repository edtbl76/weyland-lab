# Flow: machine-inventory catalog (B129 · verify gate B169)

Collect a host's installed software → merge into the git SoT (baseline vs discretionary, decisions preserved,
host-mismatch fail-closed) → emit to the Port catalog → verify the entities read back (B169, fail-closed).
Collector is read-only; only the SoT + Port are written; verify is read-only.

```mermaid
sequenceDiagram
    autonumber
    participant OP as Operator (rogueone)
    participant COL as collect-machine-inventory.sh
    participant PM as Host package managers<br/>(snap · flatpak · apt · pip · npm · images)
    participant MRG as machine_inventory.py merge
    participant SOT as machine-inventory.yaml (git SoT)
    participant EMT as machine_inventory.py emit
    participant PORT as Port (host + installed_package)
    participant VER as machine_inventory.py verify
    OP->>COL: collect-machine-inventory.sh HOST
    COL->>PM: local, or ssh user@host (weyland=root)
    PM-->>COL: normalized kind/name/version + sources: note
    COL->>MRG: host tag then records (piped)
    MRG->>MRG: verify collected host == target (else FAIL CLOSED)
    MRG->>SOT: add new (apt/pip/image = system, else = unreviewed), preserve decisions, report absent
    OP->>SOT: curate discretionary items (keep/remove + rationale), then commit
    OP->>EMT: emit all  (reads the committed SoT)
    EMT->>PORT: upsert host + installed_package entities (status/rationale from SoT)
    OP->>VER: verify all  (read-back gate, B169)
    VER->>PORT: GET host + installed_package entities
    PORT-->>VER: entity counts
    VER->>VER: Port count == SoT count? else FAIL CLOSED (exit nonzero)
    Note over MRG,SOT: new discretionary installs land status: unreviewed — the review queue + drift signal
```

Onboarding a new client is the same path (B169 / EMA-230). Demo: [demos/machine-inventory.md](../demos/machine-inventory.md).
Runbook: [runbooks/machine-inventory.md](../runbooks/machine-inventory.md).

## Nightly drift check (B170)

Runs on rogueone (user timer, `Persistent=true`). Reconciles each reachable host into an isolated worktree,
opens/updates one inventory PR when the catalog changed, and pushes a Kuma heartbeat (down reaches Telegram).
An unreachable host is skipped, never pruned. Merging the PR is the only human step.

```mermaid
flowchart TD
    T[rogueone timer 03:45 NY<br/>Persistent, survives sleep] --> E[emit plus verify committed SoT to Port]
    E --> L{for each host}
    L -->|reachable| M[collect then merge --prune<br/>in isolated worktree]
    L -->|unreachable| S[skip host, never prune]
    M --> C{catalog changed}
    C -->|yes| PR[open or update ONE inventory PR<br/>merging IS the cataloging]
    C -->|no| OK[clean]
    PR --> DOWN[Kuma down then Telegram]
    S --> DOWN
    OK --> UP[Kuma up]
```
