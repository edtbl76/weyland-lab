#!/usr/bin/env bash
# B130 — rogueone backup: restic → lab MinIO (S3). Encrypted, deduplicated, incremental.
#
# Backs up ONLY the local-only gap — what neither GitHub (code) nor Google Drive (media) already
# protects: dotfiles, ~/.config (curated), ~/.claude memory, secrets (~/.ssh, ~/.gnupg, GNOME
# keyring, mkcert root CA), curated ~/Documents, and — for each ALLOW-LISTED git repo — its
# `git ls-files --others` (untracked WIP + gitignored .env/local data) MINUS reproducible bulk.
#
# Config (this dir): backup-paths.conf, backup-repos.conf, restic-excludes.txt.
# Secrets via .env (gitignored) — sources scripts/.env: RESTIC_REPOSITORY/RESTIC_PASSWORD/AWS_* plus
# PORT_CLIENT_ID/SECRET (Port report) and KUMA_BACKUP_PUSH_URL (dead-man's-switch heartbeat).
#
# Reporting (both fail-safe — a reporting outage never fails the backup):
#   • Port `backup` entity  → the "see" layer (status/size/history dashboard)
#   • Uptime Kuma push URL   → the ALERT (Telegram if no success ping within the heartbeat window)
#
# Setup + restore: README.md. Runs as a systemd --user timer (systemd/ units).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── credentials ─────────────────────────────────────────────────────────────────
if [[ ! -f "$DIR/.env" ]]; then
  echo "FATAL: $DIR/.env missing — copy .env.example → .env (see README.md)." >&2; exit 1
fi
set -a; . "$DIR/.env"; set +a
: "${RESTIC_REPOSITORY:?must be set (scripts/.env)}" "${RESTIC_PASSWORD:?must be set (scripts/.env)}"
command -v restic >/dev/null || { echo "FATAL: restic not installed (see README.md)." >&2; exit 1; }

trim() { printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'; }

RUN_ID="$(date -u +%Y%m%d%H%M%S)"; RUN_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; RUN_HUMAN="$(date)"
SNAP=""; REPO_SIZE=0; DATA_ADDED=0; FILES_NEW=0; FILES_CHANGED=0; DUR=0

# ── build the file list ──────────────────────────────────────────────────────────
LIST="$(mktemp)"; JSONOUT="$(mktemp)"; trap 'rm -f "$LIST" "$JSONOUT"' EXIT

while IFS= read -r raw; do
  line="$(trim "${raw%%#*}")"; [[ -z "$line" ]] && continue
  path="${line/#\~/$HOME}"
  if [[ -e "$path" ]]; then printf '%s\n' "$path" >> "$LIST"; else echo "skip (missing): $path" >&2; fi
done < "$DIR/backup-paths.conf"

# Reproducible bulk dropped from the git-repo untracked entries IN THE SCRIPT — restic will NOT
# exclude a path we hand it explicitly via --files-from (it honours an explicitly-listed target even
# if a pattern matches), so the collapsed untracked dirs (node_modules/, .next/, __pycache__/, …)
# must be filtered here or they ride in.
BULK_RE='(^|/)(node_modules|\.next|\.nuxt|\.svelte-kit|dist|build|target|out|\.gradle|\.venv|venv|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.cache|caches|\.turbo|\.parcel-cache|vendor|\.idea|\.tox|\.terraform|jdbc-drivers|wrapper|coverage|htmlcov|perf-reports|\.hypothesis|\.benchmarks|\.roadie-cache|\.playwright-mcp|\.worktrees)(/|$)|\.(pyc|class|hprof|log)$'

while IFS= read -r raw; do
  line="$(trim "${raw%%#*}")"; [[ -z "$line" ]] && continue
  repo="${line/#\~/$HOME}"
  if [[ ! -d "$repo/.git" ]]; then echo "skip (not a git repo): $repo" >&2; continue; fi
  while IFS= read -r -d '' entry; do
    [[ "$entry" =~ $BULK_RE ]] && continue
    printf '%s\n' "$repo/$entry" >> "$LIST"
  done < <(cd "$repo" && git ls-files --others --directory -z)
done < "$DIR/backup-repos.conf"

echo "backup set: $(wc -l < "$LIST") top-level entries → $RESTIC_REPOSITORY"

# ── reporters (fail-safe: always return 0) ───────────────────────────────────────
report_port() {
  local status="$1"
  [[ -n "${PORT_CLIENT_ID:-}" && -n "${PORT_CLIENT_SECRET:-}" ]] || { echo "Port creds unset — skip" >&2; return 0; }
  local tok; tok="$(curl -sf -m 20 -X POST https://api.getport.io/v1/auth/access_token \
      -H 'Content-Type: application/json' \
      -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" \
      | python3 -c 'import sys,json;print(json.load(sys.stdin).get("accessToken",""))' 2>/dev/null)" || return 0
  [[ -n "$tok" ]] || return 0
  local body; body="$(RUN_ID="$RUN_ID" RUN_HUMAN="$RUN_HUMAN" RUN_ISO="$RUN_ISO" STAT="$status" \
      SNAP="$SNAP" REPO_SIZE="$REPO_SIZE" DATA_ADDED="$DATA_ADDED" FILES_NEW="$FILES_NEW" \
      FILES_CHANGED="$FILES_CHANGED" DUR="$DUR" python3 - <<'PY'
import json,os
def n(x):
    try: return int(float(x))
    except: return 0
print(json.dumps({
 "identifier": f"rogueone-{os.environ['RUN_ID']}",
 "title": f"rogueone backup {os.environ['RUN_HUMAN']}",
 "properties": {
   "status": os.environ["STAT"], "host": "rogueone",
   "repo": os.environ.get("RESTIC_REPOSITORY",""),
   "snapshotId": os.environ.get("SNAP",""),
   "repoSizeBytes": n(os.environ.get("REPO_SIZE")), "dataAddedBytes": n(os.environ.get("DATA_ADDED")),
   "filesNew": n(os.environ.get("FILES_NEW")), "filesChanged": n(os.environ.get("FILES_CHANGED")),
   "durationSeconds": n(os.environ.get("DUR")), "finishedAt": os.environ["RUN_ISO"],
 }}))
PY
)" || return 0
  curl -sf -m 20 -X POST "https://api.getport.io/v1/blueprints/backup/entities?upsert=true&merge=true" \
      -H "Authorization: Bearer $tok" -H 'Content-Type: application/json' -d "$body" >/dev/null \
      && echo "Port: reported $status (rogueone-$RUN_ID)" || echo "Port report failed (non-fatal)" >&2
  return 0
}

ping_kuma() {  # dead-man's-switch: 'up' on success, 'down' on failure
  local status="$1" kstate msg
  [[ -n "${KUMA_BACKUP_PUSH_URL:-}" ]] || { echo "KUMA_BACKUP_PUSH_URL unset — skip heartbeat" >&2; return 0; }
  if [[ "$status" == success ]]; then kstate=up; msg="OK snap=$SNAP"; else kstate=down; msg="backup FAILED"; fi
  curl -fsS -m 15 "${KUMA_BACKUP_PUSH_URL}?status=${kstate}&msg=$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$msg")" \
      >/dev/null && echo "Kuma: pinged $kstate" || echo "Kuma ping failed (non-fatal)" >&2
  return 0
}

# ── back up ─────────────────────────────────────────────────────────────────────
STATUS=success
restic backup --json --tag scheduled --exclude-caches \
  --exclude-file "$DIR/restic-excludes.txt" --files-from-verbatim "$LIST" >"$JSONOUT" || STATUS=failure

# parse the backup summary (snapshot id, files, data added, duration)
eval "$(python3 - "$JSONOUT" <<'PY'
import sys,json,shlex
snap=fn=fc=da=dur=0; snap=""
for line in open(sys.argv[1], errors="ignore"):
    line=line.strip()
    if not line.startswith("{"): continue
    try: m=json.loads(line)
    except: continue
    if m.get("message_type")=="summary":
        snap=str(m.get("snapshot_id",""))[:8]; fn=m.get("files_new",0); fc=m.get("files_changed",0)
        da=m.get("data_added",0); dur=int(m.get("total_duration",0))
print(f"SNAP={shlex.quote(str(snap))}; FILES_NEW={int(fn)}; FILES_CHANGED={int(fc)}; DATA_ADDED={int(da)}; DUR={int(dur)}")
PY
)"
tail -1 "$JSONOUT" 2>/dev/null | grep -q summary && echo "restic summary: snap=$SNAP files_new=$FILES_NEW data_added=${DATA_ADDED}B dur=${DUR}s"

if [[ "$STATUS" == success ]]; then
  # --group-by host: the backup's path SET drifts over time (allow-list edits), and the default
  # group-by host,paths would then retain a separate lineage per path-set — bloating retention.
  restic forget --prune --group-by host --keep-daily 7 --keep-weekly 4 --keep-monthly 6 \
    || echo "forget/prune failed (non-fatal)" >&2
  restic check --read-data-subset=5% || { echo "restic check FAILED" >&2; STATUS=failure; }
  REPO_SIZE="$(restic stats --json latest 2>/dev/null | python3 -c 'import sys,json;print(int(json.load(sys.stdin).get("total_size",0)))' 2>/dev/null || echo 0)"
fi

# ── report (both fail-safe) ───────────────────────────────────────────────────────
report_port "$STATUS" || true
ping_kuma  "$STATUS" || true

echo "backup $STATUS: $RUN_ISO"
[[ "$STATUS" == success ]]
