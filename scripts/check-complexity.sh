#!/usr/bin/env bash
# B162 — complexity triage: how the lab READS complexity (deep vs tangled vs shallow), not a raw line count.
#
# Length only NOMINATES a function; the verdict comes from structure (cyclomatic density + true max-nesting)
# and from how the function compares to the rest of THIS codebase (a self-calibrating z-score). The inverse
# smell — shallow pass-through / over-split delegation — is caught in the other direction. The engine is
# scripts/lib/complexity_triage.py; the adjustable knobs live in scripts/complexity-triage.json. See
# docs/concepts/reading-complexity.md and docs/runbooks/complexity-triage.md.
#
# POSTURE: ADVISORY by default — it prints the graded findings and exits 0, exactly like graphify's
# Pillar-8 wiring. The verdict IS the stop-or-accept decision; a human reads it. `--gate` flips it to a
# blocking check (any TANGLED or SHALLOW → exit 1) once the thresholds are trusted — the documented
# promotion path, deliberately not on by default.
#
# EXIT CODES: 0 = ran (advisory, or --gate clean). 1 = --gate found TANGLED/SHALLOW. 2 = the guard could
# not run (missing lizard/tree-sitter, or the engine errored) — never a silent pass.
#
#   usage: scripts/check-complexity.sh [--gate] [path ...]
#          default paths = the real-code services + scripts (Flink Java included).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE="$ROOT/scripts/lib/complexity_triage.py"
CONFIG="${COMPLEXITY_CONFIG:-$ROOT/scripts/complexity-triage.json}"

GATE=0
if [ "${1-}" = "--gate" ]; then GATE=1; shift; fi

paths=("$@")
if [ "${#paths[@]}" -eq 0 ]; then
  paths=(
    "$ROOT/nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline"
    "$ROOT/nodes/mother/lab/weyland-platform/services/weyland-guard"
    "$ROOT/nodes/mother/lab/weyland-platform/services/weyland-tool-server"
    "$ROOT/nodes/mother/lab/weyland-platform/k8s/flink"
    "$ROOT/scripts"
  )
fi

# The engine invocation is overridable (COMPLEXITY_ENGINE) so the wrapper's DECISION logic — advisory vs
# gate vs fail-closed — is testable without the analysis deps present (bats stubs it). The ENGINE owns the
# gate: with --gate it exits 1 on the clearly-bad, high-degree findings (high-confidence TANGLED + SHALLOW),
# 0 otherwise; this wrapper propagates that. Success is marked by the "complexity triage:" summary line — its
# ABSENCE means the engine crashed (missing deps / bug), which is fail-closed to exit 2, never a silent pass.
engine_args=()
[ "$GATE" -eq 1 ] && engine_args+=(--gate)

out=""
rc=0
if [ -n "${COMPLEXITY_ENGINE:-}" ]; then
  out="$("$COMPLEXITY_ENGINE" "${engine_args[@]}" "${paths[@]}" 2>&1)" || rc=$?
else
  command -v python3 >/dev/null 2>&1 || { echo "FATAL: python3 not found on PATH." >&2; exit 2; }
  out="$(PYTHONPATH="$ROOT/scripts/lib" python3 "$MODULE" --config "$CONFIG" "${engine_args[@]}" "${paths[@]}" 2>&1)" || rc=$?
fi

printf '%s\n' "$out"

if ! printf '%s\n' "$out" | grep -q "complexity triage:"; then
  echo "FATAL: the complexity engine could not run (missing lizard/tree-sitter? — pip install -r scripts/requirements-test.txt)." >&2
  exit 2
fi

if [ "$rc" -eq 0 ]; then
  exit 0
fi
if [ "$GATE" -eq 1 ] && [ "$rc" -eq 1 ]; then
  echo "" >&2
  echo "GATE FAILED: the complexity gate blocked the build (see the GATE line above). Fix the findings, or adjust the bar in scripts/complexity-triage.json." >&2
  exit 1
fi
echo "FATAL: unexpected complexity-engine exit ($rc)." >&2
exit 2
