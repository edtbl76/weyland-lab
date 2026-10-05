#!/usr/bin/env bash
# Regenerate the embedded copy of scripts/open_webui_backup.py inside the open-webui-backup CronJob's ConfigMap
# (k8s/open-webui/backup.yaml), keeping it byte-identical (scripts/tests/open-webui-backup.bats asserts it). Run after
# editing the script. Idempotent: the file is spliced under its data key, replacing whatever sat there up to the next
# data key or `---`. Same shape as scripts/embed-placement.sh.
#
#   usage: scripts/embed-open-webui-backup.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$here/nodes/mother/lab/weyland-platform/k8s/open-webui/backup.yaml"
SCRIPT="$here/scripts/open_webui_backup.py"

for f in "$MANIFEST" "$SCRIPT"; do [ -r "$f" ] || { echo "missing $f" >&2; exit 1; }; done

tmp="$(mktemp)"
awk -v script="$SCRIPT" '
  function emit(file,  line) { while ((getline line < file) > 0) print (length(line) ? "    " line : ""); close(file) }
  $0 == "  open_webui_backup.py: |" { print; emit(script); skipping=1; next }
  skipping && ($0 == "---" || $0 ~ /^  [^ ]/) { skipping=0 }
  !skipping { print }
' "$MANIFEST" > "$tmp"
mv "$tmp" "$MANIFEST"
echo "embedded $(wc -l < "$SCRIPT") lines into $(basename "$MANIFEST")"
