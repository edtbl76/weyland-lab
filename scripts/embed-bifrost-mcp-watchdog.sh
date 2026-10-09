#!/usr/bin/env bash
# Regenerate the embedded copy of scripts/bifrost_mcp_health_check.py inside the bifrost-mcp-watchdog CronJob's
# ConfigMap (B203), keeping them byte-identical (bifrost-mcp-watchdog.bats asserts it). Run after editing the script.
# Idempotent: the file is spliced under its data key, replacing whatever sat there up to the next `---`.
#
#   usage: scripts/embed-bifrost-mcp-watchdog.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$here/nodes/mother/lab/weyland-platform/k8s/bifrost/bifrost-mcp-watchdog.yaml"
SCRIPT="$here/scripts/bifrost_mcp_health_check.py"
for f in "$MANIFEST" "$SCRIPT"; do [ -r "$f" ] || { echo "missing $f" >&2; exit 1; }; done
tmp="$(mktemp)"
awk -v script="$SCRIPT" '
  $0 == "  bifrost_mcp_health_check.py: |" { print; while ((getline line < script) > 0) print (length(line) ? "    " line : ""); close(script); skipping=1; next }
  skipping && $0 == "---" { skipping=0 }
  !skipping { print }
' "$MANIFEST" > "$tmp"
mv "$tmp" "$MANIFEST"
echo "embedded $(wc -l < "$SCRIPT") lines into $(basename "$MANIFEST")"
