# Flow: machine-inventory catalog (B129)

Collect a host's installed software → merge into the git SoT (baseline vs discretionary, decisions preserved,
host-mismatch fail-closed) → emit to the Port catalog. Collector is read-only; only the SoT + Port are written.

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
    OP->>COL: collect-machine-inventory.sh HOST
    COL->>PM: local, or ssh user@host (weyland=root)
    PM-->>COL: normalized kind/name/version + sources: note
    COL->>MRG: host tag then records (piped)
    MRG->>MRG: verify collected host == target (else FAIL CLOSED)
    MRG->>SOT: add new (apt/pip/image = system, else = unreviewed), preserve decisions, report absent
    OP->>SOT: curate discretionary items (keep/remove + rationale), then commit
    OP->>EMT: emit all  (reads the committed SoT)
    EMT->>PORT: upsert host + installed_package entities (status/rationale from SoT)
    Note over MRG,SOT: new discretionary installs land status: unreviewed — the review queue + drift signal
```

Onboarding a new client is the same path (B169 / EMA-230). Demo: [demos/machine-inventory.md](../demos/machine-inventory.md).
Runbook: [runbooks/machine-inventory.md](../runbooks/machine-inventory.md).
