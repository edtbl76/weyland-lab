#!/usr/bin/env bash
# Regenerate the embedded copy of scripts/sqlite_backup.py inside EVERY CronJob that runs it (the `sqlite_backup.py`
# data key of each manifest below), keeping them byte-identical (scripts/tests/sqlite-backup.bats asserts it). Run after
# editing the script. Idempotent: the file is spliced under its data key, replacing whatever sat there up to the next
# data key or `---`. Same shape as scripts/embed-placement.sh.
#
#   usage: scripts/embed-sqlite-backup.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P="$here/nodes/mother/lab/weyland-platform/k8s"
SCRIPT="$here/scripts/sqlite_backup.py"
MANIFESTS=("$P/open-webui/backup.yaml" "$P/woodpecker/woodpecker-backup.yaml" "$P/bifrost/bifrost-backup.yaml")

[ -r "$SCRIPT" ] || { echo "missing $SCRIPT" >&2; exit 1; }
for m in "${MANIFESTS[@]}"; do
  [ -r "$m" ] || { echo "missing $m" >&2; exit 1; }
  grep -qx '  sqlite_backup.py: |' "$m" || { echo "no '  sqlite_backup.py: |' data key in $m" >&2; exit 1; }
  tmp="$(mktemp)"
  awk -v script="$SCRIPT" '
    function emit(file,  line) { while ((getline line < file) > 0) print (length(line) ? "    " line : ""); close(file) }
    $0 == "  sqlite_backup.py: |" { print; emit(script); skipping=1; next }
    skipping && ($0 == "---" || $0 ~ /^  [^ ]/) { skipping=0 }
    !skipping { print }
  ' "$m" > "$tmp"
  mv "$tmp" "$m"
  echo "embedded $(wc -l < "$SCRIPT") lines into $(basename "$(dirname "$m")")/$(basename "$m")"
done
