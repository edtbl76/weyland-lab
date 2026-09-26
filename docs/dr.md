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
| **rogueone local-only data** | dotfiles, `~/.claude` memory, secrets, untracked repo files | `restic-backup` systemd timer ([runbooks/backups.md](runbooks/backups.md)) | MinIO `rogueone-backup` on **mother USB** (not in the NVMe mirror list) | daily 02:30 NY / 1 day | 7 daily / 4 weekly / 6 monthly | Uptime Kuma push (26h dead-man's switch) → Telegram; Port `backup` entity | `restic restore` ([demos/backup-restore.md](demos/backup-restore.md)) | **2026-08-20** (byte-identical diff) |
| **Media + documents** | courses, stems, docs | Google Drive | Google (off-site) | on save | Drive's | — | Drive download | continuous |
| **SealedSecrets controller key** | decrypts every committed SealedSecret | manual export ([runbooks/secrets.md](runbooks/secrets.md)) | off-cluster (password manager / offline) | on key rotation | — | none | `kubectl apply` the exported key | **unverified** (export date unknown) |
| **restic password + `scripts/.env`** | the restic encryption key and every credential | manual escrow ([runbooks/backups.md](runbooks/backups.md)) | password manager | on change | — | none | copy back | **unverified** |
| **Port catalog config** | blueprints, schema | IaC (B137) | GitHub (+ tofu state in `tofu-state`) | every push | full history | — | `tofu apply` | **unverified** |
| **Linear** | status, history, comments, projects, initiatives, labels, templates, views (21 entities) | `linear_backup_job` Dagster asset, read-only key ([runbooks/linear-backup.md](runbooks/linear-backup.md)) — **B194, built 2026-09-26, live once deployed** | MinIO `linear-backup` on **mother USB**, mirrored to **NVMe** by `minio-backup` | daily 05:20 NY / 1 day | 90 days (MinIO lifecycle) | `dagster-freshness-check` (failed run, or no success in 30h) | B194 Slice 2 restore drill (scratch team) | **never** (export verified against a live count, 254 = 254, 2026-09-26; a restore is Slice 2) |
| **Reproducible stores** — vector stores, hydrated datasets | rebuilt from source | hydration / land jobs ([runbooks/datasets-hydration.md](runbooks/datasets-hydration.md)) | the sources themselves | — | — | — | re-run hydration | **unverified** per store |

**Not yet catalogued (unverified coverage):** Keycloak realm and users (presumed inside the core `pg_dumpall` —
check), Grafana state outside provisioned dashboards, the Uptime Kuma PVC, DataHub metadata, and each app's PVCs.
Each one needs either a row above or a written "reproducible" reason.

## Blast radius — where the copies physically are

| Medium | Holds | Survives |
|---|---|---|
| mother **USB** (`/mnt/minio`) | MinIO itself, the `rogueone-backup` restic repo, **and** the core Postgres dumps | nothing on this disk survives the disk |
| mother **NVMe** | the MinIO bucket mirror, the data-mesh Postgres dumps | a USB failure, not a mother failure |
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
6. **Linear had no backup.** B194 Slice 1 builds the nightly snapshot; the restore drill (Slice 2) is still open.
7. **Manual escrows can't be checked.** The SealedSecrets key and the restic password have no record of when they
   were last exported.

## Adding a row (DoD Pillar 9)

A new stateful system is not done until its row states: the data, the mechanism, where the copy lands (and its
blast radius), cadence and RPO, retention, the alert when it stops, the restore command (in a runbook), and the date
of a restore test that actually ran. A reproducible system states its rebuild path instead.
