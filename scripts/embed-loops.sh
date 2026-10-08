#!/usr/bin/env bash
# embed-loops.sh — rebuild the loop-library bundle the Dagster publisher reads (B175).
#
# The loop library's source of truth is knowledge-repos/loop-library/*.md. The Dagster image is built from
# services/weyland-dagster/ and cannot read that directory, so register_bifrost_loops.py publishes a bundled copy:
# services/weyland-dagster/scripts/loop_library.json. Run this after editing any loop; check-loop-library.sh (CI
# repo-guards) fails while the bundle is stale. Refuses to write a bundle from an invalid library.
#
# Usage: bash scripts/embed-loops.sh      Exit: 0 written · 1 the library is invalid · 2 could not run
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="${LOOP_LIBRARY_DIR:-$REPO_ROOT/knowledge-repos/loop-library}"
OUT="${LOOP_LIBRARY_BUNDLE:-$REPO_ROOT/nodes/mother/lab/weyland-platform/services/weyland-dagster/scripts/loop_library.json}"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
rc=0
python3 "$REPO_ROOT/scripts/loop_library.py" bundle "$LIB" >"$tmp" || rc=$?
if [ "$rc" -ne 0 ]; then
  exit "$rc"
fi
mv "$tmp" "$OUT"
trap - EXIT
echo "embedded $(grep -c '"id":' "$OUT") loop(s) into $OUT"
