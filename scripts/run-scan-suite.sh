#!/usr/bin/env bash
# Ad-hoc run of the code-scan-suite — the per-batch DoD Pillar 7 gate (security + code-quality, 19 tools; B120).
# Clears any prior adhoc job, launches a fresh one from the CronJob, waits, and prints the findings so they can be
# triaged before "done" (fix real / document-accept phantom per docs/runbooks/code-quality.md). Runs from anywhere
# with kubectl pointed at the cluster (e.g. rogueone). Tool registry: quality-tools.yaml. The weekly CronJob is the
# safety net; this is the on-demand gate on top of it.
#   usage: scripts/run-scan-suite.sh [wait-timeout]   (default 900s)
set -euo pipefail

NS=weyland
CRONJOB=code-scan-suite
JOB=scan-suite-adhoc
TIMEOUT="${1:-900s}"

echo "→ clearing any prior ${JOB} (if present)…"
kubectl -n "$NS" delete job "$JOB" --ignore-not-found

echo "→ launching ${JOB} from cronjob/${CRONJOB}…"
kubectl -n "$NS" create job "$JOB" --from="cronjob/${CRONJOB}"

echo "→ waiting up to ${TIMEOUT} for completion…"
if kubectl -n "$NS" wait --for=condition=complete "job/${JOB}" --timeout="$TIMEOUT"; then
  echo "✓ scan complete — triage NEW critical/high below (accept phantoms with a documented reason):"
else
  echo "⚠ ${JOB} did not report complete within ${TIMEOUT} (failed or still running) — recent logs:" >&2
fi
kubectl -n "$NS" logs "job/${JOB}" --tail=200
