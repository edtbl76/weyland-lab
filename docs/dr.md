# Disaster Recovery — the backup and restore catalog

The single place that answers **"if this is lost, how do we get it back, and have we ever proven it?"** for every
system in the lab. DoD **Pillar 9** ([definition-of-done.md](definition-of-done.md)) gates on this page: a stateful
thing is not done until it has a row here with a restore procedure and a dated restore test.

> Created 2026-09-26 (B194, as its Closing Gaps prework — the catalog comes before adding one more backup). Facts
> below are read from the manifests and runbooks named in each row; **unverified** means nobody has checked it yet,
> not that it is fine.

## Principles

- **A backup you haven't restored isn't a backup.** Every row carries the date of its last restore test. "Never" is a
  gap, and it is listed below.
- **Know what you can lose (RPO).** A daily job loses up to a day. A mirror with `--remove` has **no history**: a
  deletion or corruption propagates on the next run.
- **Know the blast radius.** Everything below lives in one house, and most copies sit on mother's two disks. A copy
  on the same disk as the original protects against deleted data, not a failed disk.
- **Reproducible stores say so.** A store rebuilt from its source (vector stores, hydrated datasets) needs a
  documented rebuild path, not a backup.

## Catalog

| System | Data | Mechanism | Copy lands on | Cadence / RPO | Retention | Alert | Restore procedure | Last restore test |
|---|---|---|---|---|---|---|---|---|
| **Code + docs** | every repo | git | GitHub (`edtbl76/*`) | every push | full history | — | `git clone` | continuous (every clone) |
| **Cluster config** | manifests, Argo apps, Helm values | GitOps from the repo | GitHub | every push | full history | Argo sync status | Argo re-sync from `main` | **never** as a full rebuild |
| **MinIO buckets** — `warehouse`, `lakefs`, `aidlc-kb`, `mlflow`, `tofu-state` | data products, lakeFS objects, models, IaC state | `minio-backup` CronJob, `mc mirror --overwrite --remove` (`k8s/minio/backup.yaml`) | mother **NVMe** (PVC `minio-backup`, 50Gi) | daily 22:30 NY / 1 day | **none — mirror, no history** | `ScheduledJobStale` (critical, 26h) + `ScheduledJobFailed` | `mc mirror` back from the PVC | **never** |
| **Postgres — weyland core** | every core DB (`pg_dumpall`) | `postgres-backup` CronJob (`k8s/postgres-backup.yaml`) | **mother USB** `/mnt/minio/backups` — **the same disk as MinIO** | daily 23:30 NY / 1 day | 7 most recent | `ScheduledJobStale` (critical) + `ScheduledJobFailed` | `psql -f` the dump | **never** |
| **Postgres — data mesh** (nessie + lakefs) | catalog + versioning metadata | `pg-backup` CronJob (`k8s/data-mesh/backup.yaml`) | mother **NVMe** (PVC `data-mesh-backup`, 50Gi) | daily 23:00 NY / 1 day | 7 most recent | `ScheduledJobStale` (critical) + `ScheduledJobFailed` | `pg_restore` the dump | **never** |
| **rogueone local-only data** | dotfiles, `~/.claude` settings, secrets, untracked repo files | `restic-backup` systemd timer ([runbooks/backups.md](runbooks/backups.md)) | MinIO `rogueone-backup` on **mother USB** (not in the NVMe mirror list) | daily 02:30 NY / 1 day | 7 daily / 4 weekly / 6 monthly | Uptime Kuma push (26h dead-man's switch) → Telegram; Port `backup` entity | `restic restore` ([demos/backup-restore.md](demos/backup-restore.md)) | **2026-10-01** (byte-identical diff of mkcert + a memory file from the 02:47 snapshot, after the 09-25..29 failures and the `.build` filter change; previous 2026-08-20) |
| **Shared agent memory** (B182) | the Markdown notes every coding agent shares — `~/agent-memory/weyland` on rogueone (~214 notes + `MEMORY.md`); Claude Code's memory path is a symlink to it. The Basic Memory index (`~/.basic-memory/`) is rebuilt from the notes, so it is not state | the same `restic-backup` timer (`~/agent-memory` added to `backup-paths.conf` 2026-10-03) | MinIO `rogueone-backup` on **mother USB** (same blast radius as the row above) | daily 02:30 NY / 1 day | 7 daily / 4 weekly / 6 monthly | the restic Kuma push (above); the store itself: `agent-memory-watch` → Kuma push (once `KUMA_MEMORY_PUSH_URL` is set) | `restic restore latest --include "$HOME/agent-memory"` ([runbooks/shared-agent-memory.md](runbooks/shared-agent-memory.md) § Restore) | **2026-10-03** — on-demand snapshot `f6e36e17` (17:04) restored to scratch: **214 notes byte-identical** (`diff -r`). Note: the 10-02 and earlier snapshots hold the notes at the OLD path `~/.claude/projects/*/memory` |
| **Media + documents** | courses, stems, docs | Google Drive | Google (off-site) | on save | Drive's | — | Drive download | continuous |
| **SealedSecrets controller key** | decrypts every committed SealedSecret | manual export ([runbooks/secrets.md](runbooks/secrets.md)) | off-cluster (password manager / offline) | on key rotation | — | none | `kubectl apply` the exported key | **unverified** (export date unknown) |
| **restic password + `scripts/.env`** | the restic encryption key and every credential | manual escrow ([runbooks/backups.md](runbooks/backups.md)) | password manager | on change | — | none | copy back | **unverified** |
| **Port catalog config** | blueprints, schema | IaC (B137) | GitHub (+ tofu state in `tofu-state`) | every push | full history | — | `tofu apply` | **unverified** |
| **Linear** | status, history, comments, projects, initiatives, labels, templates, views (21 entities) | `linear_backup_job` Dagster asset, read-only key ([runbooks/linear-backup.md](runbooks/linear-backup.md)) — **B194, LIVE 2026-09-27** (`git-473df840`) | MinIO `linear-backup` on **mother USB**, mirrored to **NVMe** by `minio-backup` | daily 05:20 NY / 1 day | 90 days (MinIO lifecycle) | `dagster-freshness-check` (failed run, or no success in 30h) | `scripts/linear_restore.py` ([runbooks/linear-backup.md](runbooks/linear-backup.md) § Restore) | **2026-09-27** — drill: 3 issues + 23 comments (threads, parent link) restored into a scratch team, every field verified, torn down |
| **Linear lakehouse tables** (`iceberg.linear.*` + the 3 `mart_linear_*`) | derived from the newest snapshot | rebuilt by `linear_lakehouse_tables` + dbt | — | nightly | — | — | re-run `linear_backup_job`, rebuild the marts | reproducible (no backup needed) |
| **Open WebUI** | users, chats, settings (incl. the `agent-memory` tool-server connection), model presets — `webui.db` + `vector_db/` + `uploads/` on PVC `open-webui-data` | `open-webui-backup` CronJob: SQLite online backup API + tarballs, fails closed (`k8s/open-webui/backup.yaml`, `scripts/sqlite_backup.py`) — added 2026-10-04 | mother **NVMe** (PVC `open-webui-backup`) | daily 23:45 NY / 1 day | 7 most recent | `ScheduledJobStale` (critical, 26h) + `ScheduledBackupFailed` (critical) | [runbooks/open-webui.md](runbooks/open-webui.md) § Restore | **2026-10-04** — non-destructive drill on backup `20261005T031438Z`: integrity ok, users 2 / chats 3 / models 1 (match live), the `agent-memory` connection present, both archives readable. Full restore (overwrite) not yet exercised |
| **Woodpecker CI** | users, repos + trust flags, repo **secrets** (in the clear), the `nightly-images` cron, pipeline history — `woodpecker.sqlite` on PVC `data-woodpecker-server-0` | `woodpecker-backup` CronJob: SQLite online backup API, fails closed (`k8s/woodpecker/woodpecker-backup.yaml`, `scripts/sqlite_backup.py`) — added 2026-10-05 (B201) | mother **NVMe** (PVC `woodpecker-backup`) | daily 23:50 NY / 1 day | 7 most recent | `ScheduledJobStale` (critical, 26h) + `ScheduledBackupFailed` (critical) | [runbooks/woodpecker.md](runbooks/woodpecker.md) § Backup + restore | **2026-10-05** — non-destructive drill on backup `20261006T025115Z`: integrity ok, users 1 / pipelines 284 (match the manifest), tables incl. `repos`, `secrets`, `crons`, `log_entries`. Full restore (overwrite) not yet exercised |
| **Bifrost** (agent edge) | provider keys, virtual keys + governance (budgets, model configs, pricing), MCP clients + OAuth configs, the Prompt Repository (~280) and Skills Repository (~589) — `config.db` on PVC `bifrost-data` (local-path, mother's disk). `logs.db` (request logs) is not backed up: observability history, recreated empty | `bifrost-backup` CronJob: SQLite online backup API, fails closed (`k8s/bifrost/bifrost-backup.yaml`, `scripts/sqlite_backup.py`) — added 2026-10-08 (B202 Closing Gaps) | mother **NVMe** (PVC `bifrost-backup`) | daily 23:55 NY / 1 day | 7 most recent | `ScheduledJobStale` (critical, 26h) + `ScheduledBackupFailed` (critical) | [runbooks/mcp-gateway.md](runbooks/mcp-gateway.md) § Bifrost backup + restore | **2026-10-08** — non-destructive drill on backup `20261008T200346Z`: integrity ok; providers 22, virtual keys 4, MCP clients 10, prompts 280, skills 589, matching the manifest. Full restore (overwrite) not yet exercised |
| **Reproducible stores** — vector stores, hydrated datasets | rebuilt from source | hydration / land jobs ([runbooks/datasets-hydration.md](runbooks/datasets-hydration.md)) | the sources themselves | — | — | — | re-run hydration | **unverified** per store |

**Not yet catalogued (unverified coverage):** Keycloak realm and users (presumed inside the core `pg_dumpall` —
check), Grafana state outside provisioned dashboards, the Uptime Kuma PVC, DataHub metadata, and each app's PVCs.
Each one needs either a row above or a written "reproducible" reason.

## Blast radius — where the copies physically are

| Medium | Holds | Survives |
|---|---|---|
| mother **USB** (`/mnt/minio`) | MinIO itself, the `rogueone-backup` restic repo, **and** the core Postgres dumps | nothing on this disk survives the disk |
| mother **NVMe** | the MinIO bucket mirror, the data-mesh Postgres dumps, the Open WebUI, Woodpecker and Bifrost backups | a USB failure, not a mother failure |
| GitHub | code, config, IaC | anything local |
| Google Drive | media and documents | anything local |
| **Off-site copy of lab data** | **none** | — |

## Closing Gaps — known gaps, found while writing this page

1. **Core Postgres dumps sit on the same USB disk as MinIO.** A USB failure loses both the database copies and the
   object store. Fix: land the dumps on NVMe (like `pg-backup`) or add them to the mirror.
2. **The three cluster backups have never had a restore drill.** They alert when they fail to run, but nobody has
   proven the dumps and mirror restore.
3. **The MinIO mirror has no history.** `--remove` propagates a bad delete within a day. Fix: versioned copies or
   dated snapshots.
4. **`rogueone-backup` is not mirrored to NVMe.** It lives only on the USB disk.
5. **No off-site copy of lab data** ([runbooks/backups.md](runbooks/backups.md) § Offsite has the 3-2-1 plan).
6. **Linear had no backup.** Closed 2026-09-27: nightly snapshot (B194 Slice 1) + a passing restore drill (Slice 2). Limit: the Free plan caps issues at 250, so a full-workspace restore needs archiving or a temporary upgrade. Alert drill 2026-09-27: a skipped run fired `DagsterJobStale` → Telegram.
7. **Manual escrows can't be checked.** The SealedSecrets key and the restic password have no record of when they
   were last exported.
8. **Open WebUI had no backup** — users, chats, settings and the memory tool-server connection lived only on its PVC,
   and its image was unpinned `:main`, so any restart could migrate the database with no copy. Found 2026-10-04 when
   the 0.11.4 upgrade needed a backup first. Closed: nightly `open-webui-backup` + the image pinned by digest; restore
   drill passed 2026-10-04 (non-destructive).
9. **Bifrost had no backup** — its whole configuration (provider and virtual keys, governance, MCP clients, ~280 prompts,
   ~589 skills) lived only in `config.db` on a 1 GiB PVC, and the v2 upgrade (B202) migrates that database. Found
   2026-10-08 while scoping B202. Closed 2026-10-08: nightly `bifrost-backup` (23:55 NY); first backup and a non-destructive restore drill
   passed the same day.

## Adding a row (DoD Pillar 9)

A new stateful system is not done until its row states: the data, the mechanism, where the copy lands (and its
blast radius), cadence and RPO, retention, the alert when it stops, the restore command (in a runbook), and the date
of a restore test that actually ran. A reproducible system states its rebuild path instead.
