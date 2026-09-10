#!/usr/bin/env bash
# B104 — perf regression ratchet. Reads the committed perf baseline
# (tests/perf/baseline.tsv, appended by scripts/perf-baseline.sh + trino-baseline.sh)
# and, per target, checks the LATEST run against the established FLOOR — the best
# (lowest) p95 among that target's prior runs. A run whose p95 has drifted above
# the floor by more than the tolerance, or whose error rate exceeds the ceiling,
# is a regression.
#
# ADVISORY by default (always exit 0) — perf on this node is on-demand and
# bounded, so a first pass has little variance data and the ratchet is a signal,
# not yet a gate. Arm it with PERF_RATCHET_ENFORCE=1 to exit non-zero on any
# regression (e.g. once a target has several stable runs recorded).
#
# FAIL-CLOSED: a missing baseline, a malformed row, or a non-numeric p95/err is a
# loud error (exit 2), never a silent pass — the whole point of the perf work is
# that an absent or garbled result must not read as "no regression".
#
#   env: PERF_BASELINE_FILE (default tests/perf/baseline.tsv)
#        PERF_RATCHET_TOL    (p95 tolerance fraction, default 0.25 = 25%)
#        PERF_RATCHET_ERRCEIL(max tolerated latest err_pct, default 1.0)
#        PERF_RATCHET_ENFORCE(1 = exit 1 on regression; default advisory)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE="${PERF_BASELINE_FILE:-$REPO_ROOT/tests/perf/baseline.tsv}"
TOL="${PERF_RATCHET_TOL:-0.25}"
ERRCEIL="${PERF_RATCHET_ERRCEIL:-1.0}"
ENFORCE="${PERF_RATCHET_ENFORCE:-0}"

die() { printf 'error: %s\n' "$*" >&2; exit 2; }

# ratchet_report <tsv-file> <tol> <errceil> -> prints the table + a trailing
# `REGRESSIONS <n>` line; returns 0 always (the caller decides on enforcement).
# Emits nothing but the error path to stderr; all verdict logic is here so bats
# can drive it directly with fixture files.
ratchet_report() {
  local file="$1" tol="$2" errceil="$3"
  [ -f "$file" ] || { echo "baseline not found: $file" >&2; return 2; }
  awk -F'\t' -v tol="$tol" -v errceil="$errceil" '
    NR==1 {
      # Map header names to column indexes so a column reorder cannot silently
      # shift which field we read as p95 (a classic quiet-failure).
      for (i=1;i<=NF;i++) col[$i]=i
      for (need in wanted) delete wanted[need]
      split("target p95_ms err_pct", req, " ")
      for (k in req) if (!(req[k] in col)) { print "malformed header: missing " req[k] > "/dev/stderr"; exit 3 }
      ti=col["target"]; pi=col["p95_ms"]; ei=col["err_pct"]
      next
    }
    NF==0 { next }
    {
      t=$ti; p=$pi; e=$ei
      if (t=="" || p !~ /^[0-9]+(\.[0-9]+)?$/ || e !~ /^[0-9]+(\.[0-9]+)?$/) {
        printf "malformed row %d: target=%s p95=%s err=%s\n", NR, t, p, e > "/dev/stderr"; bad=1; exit 4
      }
      order[t]=order[t]==""? NR : order[t]   # first-seen (unused, kept for clarity)
      n[t]++
      lastp[t]=p; laste[t]=e; lastn[t]=NR    # latest row wins (file is append-order)
      prevrow[t","n[t]]=p
    }
    END {
      if (bad) exit 4
      # Recompute the floor = min p95 among all rows EXCEPT each target latest.
      # Second pass over stored per-target p95 values.
      regs=0
      printf "%-12s %8s %8s %8s %7s  %s\n", "target","latest","floor","delta%","err%","verdict"
      for (t in n) {
        if (n[t] < 2) {
          printf "%-12s %8s %8s %8s %7s  %s\n", t, lastp[t], "-", "-", laste[t], "no-prior (advisory)"
          continue
        }
        floor=""
        for (k=1;k<=n[t]-1;k++) { v=prevrow[t","k]; if (floor==""||v+0<floor+0) floor=v }
        # delta vs floor
        delta = (floor+0>0)? (lastp[t]+0-floor)/(floor+0)*100 : 0
        verdict="ok"
        if (lastp[t]+0 > floor*(1.0+tol)) { verdict="REGRESSION p95"; regs++ }
        if (laste[t]+0 > errceil+0)       { verdict=(verdict=="ok"?"REGRESSION err":verdict" +err"); if (verdict !~ /p95/) regs++ }
        printf "%-12s %8.1f %8.1f %+8.1f %7s  %s\n", t, lastp[t], floor, delta, laste[t], verdict
      }
      printf "REGRESSIONS %d\n", regs
    }
  ' "$file"
  return "${PIPESTATUS[0]:-0}"
}

# lib seam for bats
[ -n "${PERF_RATCHET_LIB:-}" ] && return 0

out="$(ratchet_report "$BASELINE" "$TOL" "$ERRCEIL")"; rc=$?
[ "$rc" -eq 0 ] || die "ratchet could not evaluate the baseline (rc=$rc) — see stderr"
printf '%s\n' "$out"
regs="$(printf '%s\n' "$out" | awk '/^REGRESSIONS /{print $2}')"
[ -n "$regs" ] || die "ratchet produced no verdict line"
if [ "$regs" -gt 0 ]; then
  printf '\n%s regression(s) vs floor (tol=%s errceil=%s%%).\n' "$regs" "$TOL" "$ERRCEIL"
  [ "$ENFORCE" = "1" ] && exit 1
  printf 'advisory mode — not failing. Set PERF_RATCHET_ENFORCE=1 to gate.\n'
else
  printf '\nno regressions.\n'
fi
exit 0
