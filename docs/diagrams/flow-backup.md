# Flow: rogueone backup — restic → MinIO + reporting (B130)

How rogueone's daily backup runs and reports. A systemd **user** timer (02:30 NY + jitter) fires the script, which
builds a file list — the static include roots **plus**, for each allow-listed git repo, `git ls-files --others`
(untracked + gitignored) with reproducible bulk filtered out **in the script** (restic won't exclude a path handed
to it explicitly). restic backs that up encrypted+deduped to the lab MinIO, prunes, and does a light integrity
check. Then it reports to **both** layers: a Port `backup` entity (the "see" dashboard) and an Uptime Kuma **push**
heartbeat (the dead-man's-switch → Telegram if it ever goes silent). Both reporters are fail-safe — a reporting
outage never fails the backup.

```mermaid
sequenceDiagram
    participant T as systemd --user timer (02:30 NY)
    participant S as restic-backup.sh (rogueone)
    participant G as git (per allow-listed repo)
    participant R as restic
    participant M as MinIO s3:…:30990/rogueone-backup
    participant P as Port (backup blueprint + dashboard)
    participant K as Uptime Kuma (push → Telegram)
    T->>S: start restic-backup.service
    S->>S: read backup-paths.conf (static roots) + backup-repos.conf (allow-list)
    S->>G: git ls-files --others --directory (untracked + gitignored)
    G-->>S: entries → filter BULK_RE (node_modules/.next/__pycache__/caches…)
    S->>R: restic backup --files-from-verbatim <list> --exclude-caches --exclude-file …
    R->>M: encrypted + deduped blobs (~415M repo)
    S->>R: forget --prune --group-by host (keep 7d/4w/6m) + check --read-data-subset=5%
    alt success
        S->>P: upsert backup entity {status:success, snapshotId, repoSize, duration}
        S->>K: push ?status=up  (heartbeat — resets the 26h dead-man's-switch)
    else failure
        S->>P: upsert backup entity {status:failure}
        S->>K: push ?status=down (Kuma pages Telegram)
    end
    Note over K: no ping within ~26h → Kuma fires Telegram (catches a silently-stopped timer)
    Note over M: 3-domain model — code→GitHub, media→Google Drive, everything-else-local→here
```
