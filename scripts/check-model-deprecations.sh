#!/usr/bin/env bash
# check-model-deprecations.sh — repo guard (B223): fail when any config or code names an Anthropic model that is
# retired, or deprecated with its retirement date inside 30 days. On 2026-10-18 a Haiku 3.5 retirement email took four
# manual checks to answer "do we use it?" (we did not) — and nothing would have told us if we had.
#
# The decisions live in scripts/model_lifecycle.py (shared with the nightly anthropic-model-watch CronJob, which checks
# the running gateways); the lifecycle data in scripts/anthropic-models.json, copied from Anthropic's deprecations page.
# Scanned: config and code. Not scanned: docs, history, tests, the vendored agent framework (.claude/, Bedrock IDs on
# Bedrock's own schedule), notebook outputs.
#
# Fail-closed exit contract (estate convention): 0 = no retired / retiring model in use · 1 = one is, named file:line
# with its replacement · 2 = could not check (no or malformed manifest, nothing scanned) — never "clean".
#
#   usage: scripts/check-model-deprecations.sh          (SCAN_ROOT / MODEL_MANIFEST / MODEL_GUARD_TODAY for fixtures)
# Runbook: docs/runbooks/model-deprecations.md
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v python3 >/dev/null || { echo "check-model-deprecations: CANNOT RUN — python3 not found" >&2; exit 2; }
python3 "$here/scripts/model_lifecycle.py" scan "${SCAN_ROOT:-$here}"
