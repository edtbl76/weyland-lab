#!/usr/bin/env bash
# B190 — issue-readiness scorer: is a Linear issue ready to hand to a coding agent? The lab's replacement for SpecBot.
#
#   scripts/issue-readiness.sh EMA-249                  score one issue, upsert its one comment
#   scripts/issue-readiness.sh EMA-249 --no-comment     score only (prints the breakdown)
#   scripts/issue-readiness.sh --sweep                  every open High issue in Weyland Lab (the lean-CI step)
#
# Exit 0 READY (>= 80, no blockers) or skipped · 1 NOT READY · 2 scorer unavailable / invalid / usage — never a guessed
# score. Credentials come from scripts/.env when it exists (LITELLM_API_KEY, LINEAR_API_KEY); in CI from step secrets.
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
