# Flow: keeping mother out of overnight memory stalls (B199)

mother (78 Gi, no swap) ran so close to its memory ceiling that an overnight job plus a CI run tipped it into
page-cache thrash: node-exporter went silent, the Woodpecker agents lost the API server, CI runs died with `task
expired`, and once the node went NotReady. The fix has three parts:
- **Make room:** four idle Tier-2 stores are parked by default (replicas 0 in git), switched only through git by
  `store-park.sh`.
- **See a stall:** a memory-pressure alert (`NodeMemoryThrashing`) and a scrape-gap alert (`NodeFroze`).
- **Prove it held:** a nightly check against written thresholds.

See [runbooks/node-capacity.md](../runbooks/node-capacity.md) and [demos/node-memory.md](../demos/node-memory.md).

```mermaid
sequenceDiagram
    participant O as owner
    participant SP as store-park.sh
    participant G as git (replicas line)
    participant A as Argo (selfHeal)
    participant ST as Tier-2 store (cassandra, mongodb, cockroachdb, superset-worker)
    participant DH as DataHub ingestion schedule
    participant N as mother (node-exporter, kubelet)
    participant P as Prometheus rules
    participant TG as Telegram
    Note over SP,ST: Parked by default - frees about 9 GB (MemAvailable 2.7-6 to 12.0 GB)
    O->>SP: wake cockroachdb (to hydrate or query it)
    SP->>G: set replicas 1 (one line)
    SP->>DH: resume its schedule, read back, fingerprint unchanged
    O->>G: push
    A->>ST: apply replicas 1 (a live kubectl scale would be reverted in about 3 min)
    O->>SP: wait cockroachdb
    SP-->>O: Ready (1/1), exit 0, or exit 1 if not Ready in 10 min
    Note over P: its Down alert compares running to DESIRED, so a parked store stays silent
    O->>SP: park cockroachdb, then push
    SP->>DH: pause its schedule
    loop every scrape
        N->>P: memory stall pressure (PSI) and up
        alt PSI above 10% for 2 min
            P->>TG: NodeMemoryThrashing (replayed 4 fires in 13.5 days, all at real freezes)
        else node-exporter stops answering (a freeze)
            P->>TG: NodeFroze (one per freeze episode)
        end
    end
    Note over O,N: Night check 07:00 NY - min MemAvailable, 840 samples, Ready, PSI peak under 0.10, the 01:00 run finished
```
