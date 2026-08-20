# B130 — rogueone backups (restic → lab MinIO)

rogueone's only active backup. Encrypted, deduplicated, incremental restic snapshots to the lab
MinIO (S3), on a daily off-hours systemd timer. Replaces the removed Déjà Dup / duplicati (both
dormant, pruned in B129).

## What it backs up — and what it deliberately doesn't

Three protection domains, each thing in exactly one:

| Domain | Home | Covered by |
|---|---|---|
| **Code** | GitHub | the git repos' *committed* files |
| **Media / docs** | Google Drive | GuitarBooksAndTab, music stems, etc. |
| **Everything local-only** | **here (restic → MinIO)** | the gap nothing else protects |

So restic captures only the **local-only gap**: dotfiles, `~/.config` (curated), `~/.claude`
memory, secrets (`~/.ssh`, `~/.gnupg`, GNOME keyring, mkcert root CA), curated `~/Documents`, and —
for each **allow-listed** git repo — its `git ls-files --others` (untracked WIP + gitignored
`.env`/local data) **minus** reproducible bulk. ~740M today.

- Include roots: [`backup-paths.conf`](backup-paths.conf)
- Git-repo allow-list: [`backup-repos.conf`](backup-repos.conf) (only these repos are touched; committed code is skipped — it's on the remote)
- Excludes: [`restic-excludes.txt`](restic-excludes.txt) + restic `--exclude-caches`

Excluded on purpose: `.docker`/`snap`/toolchains/caches, `.local/bin`, non-allow-listed repos,
Drive-mirrored media, ISOs, Games, Music, `rag-embed`/`hermes-build`/`Applications`/
`DataspellProjects`, CI agent workdirs.

## One-time setup

1. **Install restic** (rogueone):
   ```
   sudo apt-get update && sudo apt-get install -y restic
   ```
2. **Create the MinIO bucket** (uses the existing `weyland` mc alias):
   ```
   mc mb weyland/rogueone-backup
   ```
3. **Secrets** — copy the example and fill it in (`.env` is gitignored):
   ```
   cp nodes/rogueone/backup/.env.example nodes/rogueone/backup/.env
   ${EDITOR:-nano} nodes/rogueone/backup/.env
   ```
   `RESTIC_PASSWORD` encrypts the repo — **lose it and the backup is unrecoverable**; escrow it in a
   password manager, not only on this box. `AWS_*` = the MinIO keys (same as the `weyland` mc alias).
4. **Initialize the repo** (once):
   ```
   set -a; . nodes/rogueone/backup/.env; set +a; restic init
   ```
5. **First backup** (foreground, to watch it):
   ```
   nodes/rogueone/backup/restic-backup.sh
   ```

## Schedule (systemd --user)

```
cp nodes/rogueone/systemd/restic-backup.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now restic-backup.timer
loginctl enable-linger edwardmangini      # so it runs without an active login
```
Daily ~02:30 NY (+jitter), `Persistent=true` catches missed runs. Logs:
`journalctl --user -u restic-backup`. List timers: `systemctl --user list-timers`.

## Restore test — REQUIRED (a backup you haven't restored isn't a backup)

Restore a known file to a scratch dir and diff it against the live copy:
```
set -a; . nodes/rogueone/backup/.env; set +a
restic snapshots
restic restore latest --target /tmp/restore-test --include "$HOME/.claude/projects"
diff -r "$HOME/.claude/projects/"*/memory /tmp/restore-test/"$HOME"/.claude/projects/*/memory && echo "RESTORE OK"
rm -rf /tmp/restore-test
```
Run this after the first backup and whenever the include set changes materially.

## Operate

- Snapshots: `restic snapshots` · browse one: `restic ls latest`
- Manual run: `systemctl --user start restic-backup.service` (or run the script)
- Full integrity: `restic check --read-data` (the timer does a 5% `--read-data-subset` each run)
- Retention: keep-daily 7 / keep-weekly 4 / keep-monthly 6 (in the script's `restic forget --prune`)

## Notes / gotchas
- `restic` needs `RESTIC_REPOSITORY` + `RESTIC_PASSWORD` + `AWS_*` in the environment — the script
  sources `.env`; interactive `restic` commands need `set -a; . .env; set +a` first.
- MinIO endpoint is the LAN NodePort `192.168.1.243:30990` (S3 over HTTP; the repo is encrypted, so
  plaintext HTTP on the LAN is fine — Google/MinIO never sees cleartext).
- The git-repo policy uses `git ls-files --others --directory`; a repo checked out with a
  `GRADLE_USER_HOME` or similar *inside* it will surface large cache dirs — add them to
  `restic-excludes.txt` (CACHEDIR.TAG-tagged ones are already caught by `--exclude-caches`).
- Offsite (3-2-1) is a future add: `restic copy` a curated subset to a Google-Drive rclone repo.
