# Flow: SQLite app-store backups — Open WebUI + Woodpecker + Bifrost (2026-10-04 / 05 / 08)

Three apps keep their whole state in ONE SQLite file in WAL mode on a RWO PVC on mother: Open WebUI (`webui.db` — users,
chats, settings, presets), Woodpecker (`woodpecker.sqlite` — users, repos, CI secrets, the nightly cron, pipeline
history, step logs) and Bifrost (`config.db` — providers and keys, virtual keys and budgets, MCP clients, ~280 prompts,
~589 skills, the owned `client_config`; B202, before its v2 migration; its request-log `logs.db` is not backed up). One script, `scripts/sqlite_backup.py`, embedded byte-identical into each CronJob's ConfigMap,
backs all three up; each job declares which tables must be non-empty. A backup that proves nothing fails CLOSED and pages.
Runbooks: [open-webui.md](../runbooks/open-webui.md) · [woodpecker.md](../runbooks/woodpecker.md) § Backup + restore ·
[mcp-gateway.md](../runbooks/mcp-gateway.md) § Bifrost backup + restore ·
catalog [dr.md](../dr.md) · demo [sqlite-backups.md](../demos/sqlite-backups.md).

```mermaid
sequenceDiagram
    participant CJ as CronJob (open-webui-backup 23:45 · woodpecker-backup 23:50 · bifrost-backup 23:55 NY)
    participant S as sqlite_backup.py
    participant D as data PVC (live db, WAL)
    participant B as backup PVC (mother NVMe)
    participant K as kube-state-metrics + Prometheus
    participant A as Alertmanager to Telegram

    CJ->>S: --db FILE --require TABLE ... --keep 7 /data /backup/APP
    S->>B: mkdir .inprogress-TIMESTAMP
    S->>D: SQLite online backup API (consistent, includes WAL-only commits)
    D-->>B: snapshot written into .inprogress-TIMESTAMP
    S->>S: integrity_check = ok, every --require table present and non-empty
    S->>B: tar --archive dirs (Open WebUI: vector_db, uploads)
    S->>B: manifest.json LAST (integrity, counts, files), then rename to TIMESTAMP
    S->>B: rotate - keep the newest 7, delete interrupted .inprogress runs
    S-->>CJ: exit 0 (sqlite-backup OK ... counts=...)
    alt missing db, corrupt copy, or an empty or missing required table
        S->>B: delete .inprogress-TIMESTAMP (nothing that looks like a backup)
        S-->>CJ: exit 2
        K->>A: ScheduledBackupFailed (critical)
    end
    alt no successful run for 26h (stuck, suspended, image gone)
        K->>A: ScheduledJobStale (critical)
    end
    Note over B: Restore drill (non-destructive) - a throwaway pod opens the newest copy READ-ONLY, checks integrity, counts and tables
```

**Woodpecker's database lock fix rides the same store (B201).** `WOODPECKER_DATABASE_MAX_CONNECTIONS: '1'` makes
Woodpecker queue its own writes (metrics, cron list, lease extensions, step logs) instead of racing inside SQLite; the
Loki ruler pages `WoodpeckerDatabaseLocked` / `WoodpeckerTaskExpired` if a lock or a killed run ever returns.
