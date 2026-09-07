#!/usr/bin/env bash
# On-demand mutation check (B152 category 5 — mutation testing).
#
# NOT a standing CI lane, by design: mutation testing is slow and expensive, and this is a solo $0 lab.
# It is a targeted, on-demand test-QUALITY check — it injects bugs into a source module and re-runs that
# module's tests; a KILLED mutant means the tests caught the bug, a SURVIVED mutant is a coverage gap the
# tests should close. Run it against the highest-value pure leaves (the transform/collect functions whose
# correctness the whole mesh depends on) after changing them or their tests.
#
# Proven 2026-09-06: `_collect` (the autodiscovery collector whose bug took the code server down) scored
# 5/5 mutants killed — its example + property tests catch every mutation.
#
#   usage: scripts/run-mutation.sh [<module-path> "<pytest args>"]
#     default target: weyland_pipeline/assets/_collect.py + its example/property tests
#     other leaves, e.g.:
#       scripts/run-mutation.sh weyland_pipeline/assets/datasets_lib/land_core.py "tests/test_land_core.py"
#       scripts/run-mutation.sh weyland_pipeline/assets/datasets_lib/domain_job_plan.py "tests/test_domain_job_plan.py tests/test_property_based.py"
#
# deps (on-demand, NOT in the fast lane): pip install mutmut==2.5.1 pytest hypothesis + the target's test
# deps (pyarrow/pandas for the parse leaves). Run in python:3.12-slim like the other lanes if you prefer.
set -euo pipefail

SVC="nodes/mother/lab/weyland-platform/services/weyland-dagster"
MOD="${1:-weyland_pipeline/assets/_collect.py}"
TESTS="${2:-tests/test_collect.py tests/test_property_based.py}"

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/$SVC"

command -v mutmut >/dev/null 2>&1 || {
  echo "mutmut not installed — this is an on-demand tool: pip install mutmut==2.5.1 pytest hypothesis" >&2
  exit 2
}

echo "→ mutating $MOD against: $TESTS"
mutmut run --paths-to-mutate "$MOD" --runner "python -m pytest -q -x $TESTS" || true
echo "── results ─────────────────────────────────"
mutmut results
echo "A SURVIVED (🙁) mutant = the tests did not catch that injected change — expand the tests."
