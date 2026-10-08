#!/usr/bin/env bash
# check-loop-library.sh — repo guard for the loop library (B175, CI repo-guards).
#
# 1. Every loop in knowledge-repos/loop-library/ is valid: required fields, a known category, the id matching the file
#    name, a non-empty prompt, and a checkable terminal condition (EMA-233: an entry without one is not accepted).
# 2. The published bundle (services/weyland-dagster/scripts/loop_library.json) is byte-identical to a fresh bundle of
#    the Markdown. The Dagster publisher reads the bundle, so a stale one silently serves old loops.
#
# Usage: bash scripts/check-loop-library.sh
# Exit:  0 valid and in sync · 1 an invalid loop or a stale/missing bundle · 2 could not run (no library, no python)
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="${LOOP_LIBRARY_DIR:-$REPO_ROOT/knowledge-repos/loop-library}"
BUNDLE="${LOOP_LIBRARY_BUNDLE:-$REPO_ROOT/nodes/mother/lab/weyland-platform/services/weyland-dagster/scripts/loop_library.json}"

command -v python3 >/dev/null || { echo "check-loop-library: python3 not found" >&2; exit 2; }

python3 "$REPO_ROOT/scripts/loop_library.py" validate "$LIB"
rc=$?
[ "$rc" -eq 0 ] || exit "$rc"

fresh="$(mktemp)"
trap 'rm -f "$fresh"' EXIT
python3 "$REPO_ROOT/scripts/loop_library.py" bundle "$LIB" >"$fresh" || exit 2
if [ ! -f "$BUNDLE" ] || ! cmp -s "$fresh" "$BUNDLE"; then
  echo "loop-library: bundle is stale or missing ($BUNDLE) — run: bash scripts/embed-loops.sh"
  exit 1
fi
echo "loop-library: bundle in sync ($BUNDLE)"
