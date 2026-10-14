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
# A bare integer (e.g. `900`) is a natural way to pass the wait, but `kubectl wait --timeout` REQUIRES a unit
# ("missing unit in duration") and fails the wait — the job runs on, but the script reports it never completed.
# Normalize a unitless number to seconds so the arg can't silently break the wait.
[[ "$TIMEOUT" =~ ^[0-9]+$ ]] && TIMEOUT="${TIMEOUT}s"

echo "→ clearing any prior ${JOB} (if present)…"
kubectl -n "$NS" delete job "$JOB" --ignore-not-found

echo "→ launching ${JOB} from cronjob/${CRONJOB}…"
kubectl -n "$NS" create job "$JOB" --from="cronjob/${CRONJOB}"

echo "→ waiting up to ${TIMEOUT} for completion…"
complete=1
if kubectl -n "$NS" wait --for=condition=complete "job/${JOB}" --timeout="$TIMEOUT"; then
  echo "✓ scan complete — triage NEW critical/high below (accept phantoms with a documented reason):"
else
  complete=0
  echo "⚠ ${JOB} did not report complete within ${TIMEOUT} (failed or still running) — recent logs:" >&2
fi
kubectl -n "$NS" logs "job/${JOB}" --tail=200
# Fail closed (2026-10-14): a scan that did not finish is NOT a clean scan, so it must never exit 0. It used to: the
# B207 DoD run timed out mid-trivy, printed the warning above, and returned success. Exit 2 = the gate could not do
# its job (the partial logs above are still worth reading). Re-run with a longer wait, or read the job when it ends:
#   kubectl -n weyland wait --for=condition=complete job/scan-suite-adhoc --timeout=1800s && kubectl -n weyland logs job/scan-suite-adhoc --tail=200
if [ "$complete" -eq 0 ]; then
  echo "✗ NOT a clean scan: ${JOB} did not complete, so these findings are partial (exit 2)" >&2
  exit 2
fi
