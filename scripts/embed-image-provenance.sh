#!/usr/bin/env bash
# Regenerate the embedded copy of check-image-provenance.sh inside the image-provenance CronJob's
# ConfigMap, keeping the two byte-identical (image-provenance.bats asserts it). Run after editing the
# guard. Idempotent: it splices the current script between the ConfigMap data key and the next `---`.
#
#   usage: scripts/embed-image-provenance.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$here/scripts/check-image-provenance.sh"
MANIFEST="$here/nodes/mother/lab/weyland-platform/k8s/monitoring/image-provenance.yaml"
KEY="  check-image-provenance.sh: |"

[ -r "$SCRIPT" ]   || { echo "missing $SCRIPT" >&2; exit 1; }
[ -r "$MANIFEST" ] || { echo "missing $MANIFEST" >&2; exit 1; }

tmp="$(mktemp)"
# Everything up to and including the data-key line, then the script indented 4 spaces, then resume at
# the first `---` that follows the key.
awk -v key="$KEY" -v script="$SCRIPT" '
  $0 == key { print; while ((getline line < script) > 0) print (length(line) ? "    " line : ""); skipping=1; next }
  skipping && $0 == "---" { skipping=0 }
  !skipping { print }
' "$MANIFEST" > "$tmp"
mv "$tmp" "$MANIFEST"
echo "embedded $(wc -l < "$SCRIPT") lines into $(basename "$MANIFEST")"
