#!/usr/bin/env bash
# Regenerate the embedded copies of scripts/placement_check.py and placement.yaml inside the placement-coverage
# CronJob's ConfigMap (B198), keeping them byte-identical (placement.bats asserts it). Run after editing either — in
# practice after every new placement.yaml row. Idempotent: each file is spliced under its data key, replacing
# whatever sat there up to the next data key or `---`.
#
#   usage: scripts/embed-placement.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$here/nodes/mother/lab/weyland-platform/k8s/monitoring/placement-coverage.yaml"
SCRIPT="$here/scripts/placement_check.py"
DATA="$here/placement.yaml"

for f in "$MANIFEST" "$SCRIPT" "$DATA"; do [ -r "$f" ] || { echo "missing $f" >&2; exit 1; }; done

tmp="$(mktemp)"
awk -v script="$SCRIPT" -v data="$DATA" '
  function emit(file,  line) { while ((getline line < file) > 0) print (length(line) ? "    " line : ""); close(file) }
  $0 == "  placement_check.py: |" { print; emit(script); skipping=1; next }
  $0 == "  placement.yaml: |"     { print; emit(data);   skipping=1; next }
  skipping && ($0 == "---" || $0 ~ /^  [^ ]/) { skipping=0 }
  !skipping { print }
' "$MANIFEST" > "$tmp"
mv "$tmp" "$MANIFEST"
echo "embedded $(wc -l < "$SCRIPT") + $(wc -l < "$DATA") lines into $(basename "$MANIFEST")"
