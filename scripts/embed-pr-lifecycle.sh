#!/usr/bin/env bash
# Regenerate the embedded copy of check-pr-lifecycle.sh inside the pr-lifecycle-reconcile CronJob's
# ConfigMap, keeping the two byte-identical (pr-lifecycle.bats asserts it). Run after editing the guard.
# Idempotent: it splices the current script between the ConfigMap data key and the next `---`. Same
# pattern as scripts/embed-image-provenance.sh / embed-datahub-coverage.sh / embed-api-drift.sh.
#
#   usage: scripts/embed-pr-lifecycle.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$here/scripts/check-pr-lifecycle.sh"
MANIFEST="$here/nodes/mother/lab/weyland-platform/k8s/pr-lifecycle/pr-lifecycle-reconcile.yaml"
KEY="  check-pr-lifecycle.sh: |"

[ -r "$SCRIPT" ]   || { echo "missing $SCRIPT" >&2; exit 1; }
[ -r "$MANIFEST" ] || { echo "missing $MANIFEST" >&2; exit 1; }

tmp="$(mktemp)"
# Everything up to and including the data-key line, then the script indented 4 spaces (blank lines stay
# blank, never "    "), then resume at the first `---` that follows the key.
awk -v key="$KEY" -v script="$SCRIPT" '
  $0 == key { print; while ((getline line < script) > 0) print (length(line) ? "    " line : ""); skipping=1; next }
  skipping && $0 == "---" { skipping=0 }
  !skipping { print }
' "$MANIFEST" > "$tmp"
mv "$tmp" "$MANIFEST"
echo "embedded $(wc -l < "$SCRIPT") lines into $(basename "$MANIFEST")"
