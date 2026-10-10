#!/usr/bin/env bash
# B190 — issue readiness: does a Linear issue meet the lab's implementation-ready standard (AGENTS.md)? Replaces SpecBot.
#
#   scripts/issue-readiness.sh EMA-249                  check one issue, create/update its one comment
#   scripts/issue-readiness.sh EMA-249 --no-comment     check only (names every missing section)
#   scripts/issue-readiness.sh --sweep                  every open High issue in Weyland Lab (the lean-CI step)
#
# Exit 0 READY · 1 NOT READY · 2 Linear unavailable / usage — an error is never READY. LINEAR_API_KEY comes from
# scripts/.env when it exists; in CI from the step secret.
# ISSUE_READINESS_ENV overrides which env file is read (the tests point it at nothing). All logic lives in
# scripts/issue_readiness.py. Runbook: docs/runbooks/issue-readiness.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ISSUE_READINESS_ENV:-$REPO_ROOT/scripts/.env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

exec python3 "$REPO_ROOT/scripts/issue_readiness.py" "$@"
