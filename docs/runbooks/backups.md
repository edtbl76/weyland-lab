# Backups Runbook — rogueone (restic → MinIO, B130)

rogueone's active backup: encrypted, deduplicated, incremental **restic** snapshots to the lab **MinIO** (S3), on
a daily off-hours systemd timer, with **Port** (see) + **Uptime Kuma** (alert) reporting. Replaced the removed Déjà
Dup / duplicati (both dormant, pruned in B129). Config lives at `nodes/rogueone/{backup,systemd}`; the code-side
`nodes/rogueone/backup/README.md` carries the same commands next to the scripts.

## What it backs up — the 3-domain model

Each piece of data lives in exactly one protection domain:

| Domain | Home | Covered by |
|---|---|---|
| **Code** | GitHub | the git repos' *committed* files |
| **Media / docs** | Google Drive | GuitarBooksAndTab courses, music Stems, etc. |
| **Everything local-only** | **restic → MinIO** | the gap nothing else protects |

restic captures only the **local-only gap** (~415M deduped): dotfiles, `~/.config` (curated), `~/.claude` memory,
secrets (`~/.ssh`, `~/.gnupg`, GNOME keyring, **mkcert root CA**), curated `~/Documents`, and — for each
**allow-listed** git repo — its `git ls-files --others` (untracked WIP + gitignored `.env`/local data) **minus**
reproducible bulk. Config: `backup-paths.conf` (roots), `backup-repos.conf` (git allow-list), `restic-excludes.txt`
(+ restic `--exclude-caches`).

## Schedule

Daily **02:30 NY** (+≤30m jitter) via a systemd **user** timer on rogueone (`restic-backup.timer` →
`restic-backup.service`), `Persistent=true`, needs `loginctl enable-linger edwardmangini`. See
[schedules.md](../schedules.md). Runs on rogueone (not mother) so it doesn't stack on the single node.

## Reporting

- **Port (see):** each run upserts a `backup` entity (status/snapshotId/repoSize/duration) → the **weyland Backups**
  dashboard (status pie + counters + runs table).
- **Uptime Kuma (alert — the one that matters):** the script pings a Kuma **push** monitor on success; Kuma pages
  **Telegram** if it hears nothing within ~26h — the dead-man's-switch that catches a silently-stopped timer.
  The push endpoint is reached via a `/api/push`-only Ingress that bypasses `traefik-forward-auth` (the push token is
  its own auth; the Kuma UI stays Keycloak-gated).

## Operate

```
set -a; . nodes/rogueone/backup/.env; set +a     # loads restic + AWS(MinIO) creds from scripts/.env
restic snapshots                                  # list
systemctl --user start restic-backup.service      # run now (or: nodes/rogueone/backup/restic-backup.sh)
journalctl --user -u restic-backup                # logs
systemctl --user list-timers restic-backup.timer  # next run
```
Retention: `keep-daily 7 / keep-weekly 4 / keep-monthly 6` (`restic forget --prune --group-by host` in the script).
Integrity: the timer does a 5% `--read-data-subset` each run; full check = `restic check --read-data`.

## Restore

Restore a path to a scratch dir and diff (do this after setup and after any material scope change):
```
set -a; . nodes/rogueone/backup/.env; set +a
restic restore latest --target /tmp/restore-test --include "$HOME/.local/share/mkcert"
diff -rq "$HOME/.local/share/mkcert" /tmp/restore-test/"$HOME"/.local/share/mkcert && echo "RESTORE OK"
rm -rf /tmp/restore-test
```
Full restore: drop `--include`; restore reconstructs the absolute tree under `--target`.

## Gotchas (hard-won)

- **restic won't exclude a path you hand it explicitly** via `--files-from` — it honours an explicit target. The
  git-repo bulk (`node_modules`/`.next`/`__pycache__`/Gradle `caches`) is therefore filtered **in the script**
  (`BULK_RE`) before restic sees it. A first run ballooned to **5.1G** before this fix (target ~800M).
- **`restic forget` defaults to `--group-by host,paths`** — the backup's path SET drifts as the allow-list changes,
  which would retain a separate lineage per path-set and bloat retention. Use `--group-by host`.
- **`RESTIC_PASSWORD` is the encryption key** — lose it and the repo is unrecoverable ciphertext; escrow it (it lives
  in `scripts/.env`, but also keep it in a password manager, not only on this box).
- **Stale lock** after an interrupted prune: `restic unlock` (only when no restic process is actually running).
- MinIO endpoint is the LAN NodePort `192.168.1.243:30990` (S3 over plain HTTP — fine, the repo is encrypted
  before upload). Bucket: `rogueone-backup` (`mc mb weyland/rogueone-backup`).

## Setup (rebuild from scratch)

`sudo apt-get install -y restic` → `mc mb weyland/rogueone-backup` → put the 4 restic vars in `scripts/.env`
(`RESTIC_REPOSITORY`/`RESTIC_PASSWORD`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) → `restic init` →
`restic-backup.sh` (first run) → restore test → install the timer (see [schedules.md](../schedules.md)). Full
step-by-step: `nodes/rogueone/backup/README.md`.

## Offsite (future — 3-2-1)

MinIO is same-site (rogueone + weyland, one house). A future offsite copy = `restic copy` a curated subset to a
Google-Drive `rclone` repo (rclone also being the tool that would push any remaining media to Drive).
