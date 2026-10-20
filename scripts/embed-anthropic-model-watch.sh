#!/usr/bin/env bash
# Regenerate the embedded copies of scripts/model_lifecycle.py and scripts/anthropic-models.json inside the
# anthropic-model-watch CronJob's ConfigMap (B223), keeping them byte-identical (model-deprecations.bats asserts it).
# Run after editing either file — a manifest update after a deprecation email is the usual reason.
# Idempotent: each file is spliced under its data key, replacing whatever sat there up to the next key or `---`.
#
#   usage: scripts/embed-anthropic-model-watch.sh
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$here/nodes/mother/lab/weyland-platform/k8s/bifrost/anthropic-model-watch.yaml"
LOGIC="$here/scripts/model_lifecycle.py"
MODELS="$here/scripts/anthropic-models.json"
for f in "$MANIFEST" "$LOGIC" "$MODELS"; do [ -r "$f" ] || { echo "missing $f" >&2; exit 1; }; done
tmp="$(mktemp)"
awk -v logic="$LOGIC" -v models="$MODELS" '
  function splice(file,   line) { while ((getline line < file) > 0) print (length(line) ? "    " line : ""); close(file) }
  skipping && ($0 == "---" || $0 ~ /^  [^ ]/) { skipping=0 }
  skipping { next }
  $0 == "  model_lifecycle.py: |"    { print; splice(logic);  skipping=1; next }
  $0 == "  anthropic-models.json: |" { print; splice(models); skipping=1; next }
  { print }
' "$MANIFEST" > "$tmp"
mv "$tmp" "$MANIFEST"
echo "embedded $(wc -l < "$LOGIC") + $(wc -l < "$MODELS") lines into $(basename "$MANIFEST")"
