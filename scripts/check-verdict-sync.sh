#!/usr/bin/env bash
# check-verdict-sync.sh — architecture guard (B152): the guardrails/verdict.py wire contract is
# byte-duplicated across weyland-guard and weyland-tool-server (Hook = URL paths, Decision = parsed
# from the response). Nothing kept the two copies in sync — the exact duplication DoD Pillar 8 flagged.
# This fails when they drift, so the wire contract stays a contract.
#
# Fail-closed exit contract (the estate convention): 0 = identical · 1 = they DIFFER (a real defect) ·
# 2 = the guard could not run (a file is missing) — never conflate "could not check" with "in sync".
#
#   usage: scripts/check-verdict-sync.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Paths are overridable so the bats suite can point them at fixtures (estate convention).
A="${VERDICT_A:-$here/nodes/mother/lab/weyland-platform/services/weyland-guard/guardrails/verdict.py}"
B="${VERDICT_B:-$here/nodes/mother/lab/weyland-platform/services/weyland-tool-server/guardrails/verdict.py}"

for f in "$A" "$B"; do
  [ -f "$f" ] || { printf 'CANNOT RUN — missing %s\n' "$f" >&2; exit 2; }
done

if cmp -s "$A" "$B"; then
  printf 'OK — guardrails/verdict.py is byte-identical across weyland-guard and weyland-tool-server (%s lines).\n' "$(wc -l < "$A")"
  exit 0
fi

printf 'DRIFT — guardrails/verdict.py differs between weyland-guard and weyland-tool-server:\n' >&2
diff "$A" "$B" >&2 || true
printf 'They are one wire contract kept in sync by nothing but this guard — reconcile them.\n' >&2
exit 1
