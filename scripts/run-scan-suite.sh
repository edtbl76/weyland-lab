#!/usr/bin/env bash
# Ad-hoc run of the code-scan-suite — the per-batch DoD Pillar 7 gate (security + code-quality; roster in quality-tools.yaml; B120).
# Clears any prior adhoc job, launches a fresh one from the CronJob, waits, and prints the findings so they can be
# triaged before "done" (fix real / document-accept phantom per docs/runbooks/code-quality.md). Runs from anywhere
# with kubectl pointed at the cluster (e.g. rogueone). Tool registry: quality-tools.yaml. The weekly CronJob is the
# safety net; this is the on-demand gate on top of it.
#   usage: scripts/run-scan-suite.sh [wait-timeout]   (default 5400s — a full run took 43 min, over 60 with the B213 image scans)
set -euo pipefail

NS=weyland
CRONJOB=code-scan-suite
JOB=scan-suite-adhoc
TIMEOUT="${1:-5400s}"
# A bare integer (e.g. `900`) means seconds; `90m` / `2h` are accepted too. Anything else is a usage error (exit 2),
# never a wait that silently ends at once.
[[ "$TIMEOUT" =~ ^[0-9]+$ ]] && TIMEOUT="${TIMEOUT}s"
case "$TIMEOUT" in
  *s) WAIT_S="${TIMEOUT%s}" ;; *m) WAIT_S=$(( ${TIMEOUT%m} * 60 )) ;; *h) WAIT_S=$(( ${TIMEOUT%h} * 3600 )) ;;
  *) echo "✗ wait '${TIMEOUT}' is not <N>, <N>s, <N>m or <N>h (exit 2)" >&2; exit 2 ;;
esac
[[ "$WAIT_S" =~ ^[0-9]+$ ]] || { echo "✗ wait '${TIMEOUT}' is not a number of seconds (exit 2)" >&2; exit 2; }
POLL="${SCAN_POLL_INTERVAL:-30}"

echo "→ clearing any prior ${JOB} (if present)…"
kubectl -n "$NS" delete job "$JOB" --ignore-not-found

echo "→ launching ${JOB} from cronjob/${CRONJOB}…"
kubectl -n "$NS" create job "$JOB" --from="cronjob/${CRONJOB}"

# Poll for EITHER terminal condition (2026-10-16). `kubectl wait --for=condition=complete` never returns for a FAILED
# Job, and scan.py now fails the Job on a scan defect (exit 3, podFailurePolicy), so waiting on Complete alone sat out
# the whole timeout before saying anything.
echo "→ waiting up to ${WAIT_S}s for completion…"
state="" SECONDS=0
while :; do
  conds="$(kubectl -n "$NS" get job "$JOB" -o jsonpath='{range .status.conditions[?(@.status=="True")]}{.type}{" "}{end}' 2>/dev/null || true)"
  case " ${conds} " in
    *" Complete "*) state=complete; break ;;
    *" Failed "*) state=failed; break ;;
  esac
  [ "$SECONDS" -ge "$WAIT_S" ] && { state=timeout; break; }
  sleep "$POLL"
done
complete=0
case "$state" in
  complete)
    complete=1
    echo "✓ scan complete — every repo's critical/high totals below; triage what is NEW against the previous archive (docs/runbooks/code-quality.md):" ;;
  failed)
    echo "⚠ ${JOB} FAILED — a scan defect (a tool crashed or an image could not be scanned) or a repo failure:" >&2 ;;
  *)
    echo "⚠ ${JOB} did not report complete within ${WAIT_S}s (still running) — recent logs:" >&2 ;;
esac
# The WHOLE log, summarized (2026-10-15). This used to print `--tail=200` under "triage NEW critical/high below", but
# a full run is ~25,000 lines across ~10 repos, so the tail showed only the last two (small, clean) repos: the
# weyland-lab section, with its critical/high totals, never reached the screen. Now the full log goes to a file and the
# summary prints, per repo, every tool with a critical or high finding plus where its reports were archived.
LOG_FILE="${SCAN_LOG_FILE:-${TMPDIR:-/tmp}/scan-suite-$(date +%Y%m%dT%H%M%S).log}"
kubectl -n "$NS" logs "job/${JOB}" --tail=-1 >"$LOG_FILE" || true
if [ ! -s "$LOG_FILE" ]; then
  echo "✗ NOT a clean scan: could not read any log from job/${JOB} (exit 2)" >&2
  exit 2
fi
awk '
  /^=+ scan-suite: / { repo = $3; next }
  /^  = [A-Za-z0-9_-]+: [0-9]+C \/ [0-9]+H \// {
    tools++; split($3, c, "C"); split($5, h, "H")
    if (c[1] + 0 > 0 || h[1] + 0 > 0) print "  " (repo ? repo : "?") "  " substr($0, 5)
    next
  }
  /^  = archive: / { print "  " (repo ? repo : "?") "  " substr($0, 5) }
  END { print "  (" tools + 0 " tool result(s) read)"; if (tools == 0) exit 3 }
' "$LOG_FILE" || summary_rc=$?
echo "  full log: $LOG_FILE ($(wc -l <"$LOG_FILE") lines)"
if [ "${summary_rc:-0}" -ne 0 ] && [ "$complete" -eq 1 ]; then
  # A completed scan whose log names no tool result is not a clean scan; it's a log this summary can't read.
  echo "✗ NOT a clean scan: the job completed but its log has no '= <tool>: …C / …H' lines (exit 2)" >&2
  exit 2
fi
[ "$complete" -eq 1 ] || tail -40 "$LOG_FILE"
# Fail closed (2026-10-14): a scan that did not finish is NOT a clean scan, so it must never exit 0. It used to: the
# B207 DoD run timed out mid-trivy, printed the warning above, and returned success. Exit 2 = the gate could not do
# its job (the partial logs above are still worth reading). Re-run with a longer wait, or read the job when it ends:
#   kubectl -n weyland get job scan-suite-adhoc -o jsonpath='{.status.conditions[*].type}' ; kubectl -n weyland logs job/scan-suite-adhoc --tail=-1
if [ "$state" = failed ]; then
  grep -E '^\s*!! (SCAN DEFECT|CLONE FAILED|scan\.py returned)' "$LOG_FILE" | sed 's/^ */  /' | sort -u >&2 || true
  echo "✗ NOT a clean scan: ${JOB} FAILED — the reasons above; the counts it posted are incomplete (exit 2)" >&2
  exit 2
fi
if [ "$complete" -eq 0 ]; then
  echo "✗ NOT a clean scan: ${JOB} did not complete, so these findings are partial (exit 2)" >&2
  exit 2
fi
