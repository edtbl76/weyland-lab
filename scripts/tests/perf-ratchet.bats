#!/usr/bin/env bats
# B104 — perf regression ratchet (scripts/perf-ratchet.sh).
#
# The ratchet compares each target's LATEST perf run against the FLOOR (best/lowest p95 among its prior
# runs). The properties under test are the fail-closed ones — the same class the lab keeps getting bitten
# by (a malformed or absent result must never read as "no regression"):
#   - a real p95 drift above floor*(1+tol) is flagged; within tolerance is not.
#   - a latest error rate above the ceiling is flagged.
#   - a target with only one run is advisory (no floor to compare), never a false regression.
#   - a malformed row / bad header / missing file is a LOUD error (exit 2), never a silent pass.
#   - advisory by default (exit 0 even with regressions); PERF_RATCHET_ENFORCE=1 gates (exit 1).

setup() {
  load helper
  SCRIPT="$REPO_ROOT/scripts/perf-ratchet.sh"
  TSV="$BATS_TEST_TMPDIR/baseline.tsv"
}

hdr() { printf 'target\trps\tp50_ms\tp95_ms\tp99_ms\terr_pct\treqs\tvus\tdur\ttimestamp\n' > "$TSV"; }
row() { # row <target> <p95> <err>
  printf '%s\t100\t10\t%s\t99\t%s\t1000\t3\t20s\t2026-09-10T00:00:00Z\n' "$1" "$2" "$3" >> "$TSV"; }

run_ratchet() { PERF_BASELINE_FILE="$TSV" run bash "$SCRIPT"; }

@test "script exists" { [ -f "$SCRIPT" ]; }

@test "single run per target is advisory no-prior, zero regressions" {
  hdr; row toolserver 45 0.00
  run_ratchet
  [ "$status" -eq 0 ]
  [[ "$output" == *"no-prior"* ]]
  [[ "$output" == *"REGRESSIONS 0"* ]]
}

@test "a p95 above floor*(1+tol) is a regression" {
  hdr; row svc 20 0.00; row svc 30 0.00       # floor 20, latest 30 > 25
  run_ratchet
  [[ "$output" == *"REGRESSION p95"* ]]
  [[ "$output" == *"REGRESSIONS 1"* ]]
  [ "$status" -eq 0 ]                          # advisory by default
}

@test "enforce mode exits non-zero on a regression" {
  hdr; row svc 20 0.00; row svc 30 0.00
  PERF_BASELINE_FILE="$TSV" PERF_RATCHET_ENFORCE=1 run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"REGRESSION p95"* ]]
}

@test "a p95 within tolerance is not a regression" {
  hdr; row svc 20 0.00; row svc 24 0.00       # 24 < 20*1.25=25
  run_ratchet
  [[ "$output" == *"REGRESSIONS 0"* ]]
  [[ "$output" != *"REGRESSION p95"* ]]
  [[ "$output" != *"REGRESSION err"* ]]
}

@test "latest error rate above the ceiling is a regression" {
  hdr; row svc 20 0.00; row svc 20 2.00       # p95 flat, err 2% > 1% ceiling
  run_ratchet
  [[ "$output" == *"REGRESSION err"* ]]
  [[ "$output" == *"REGRESSIONS 1"* ]]
}

@test "floor is the MIN across prior runs and excludes the latest" {
  hdr; row svc 20 0.00; row svc 10 0.00; row svc 30 0.00   # floor=min(20,10)=10; 30>12.5
  run_ratchet
  [[ "$output" == *"REGRESSION p95"* ]]
  # floor column should read 10.0, not 20 or 30
  echo "$output" | grep -qE '^svc +30\.0 +10\.0'
}

@test "a malformed (non-numeric p95) row is a loud error, not a pass" {
  hdr; row svc 20 0.00; printf 'svc\t100\t10\tNaN\t99\t0.00\t1\t3\t20s\tt\n' >> "$TSV"
  run_ratchet
  [ "$status" -eq 2 ]
  [[ "$output" == *"malformed"* ]] || [[ "$output" == *"could not evaluate"* ]]
}

@test "a missing baseline file is a loud error" {
  PERF_BASELINE_FILE="$BATS_TEST_TMPDIR/nope.tsv" run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"not found"* ]] || [[ "$output" == *"could not evaluate"* ]]
}

@test "a header missing p95_ms is a loud error" {
  printf 'target\trps\terr_pct\ttimestamp\n' > "$TSV"
  printf 'svc\t100\t0.00\tt\n' >> "$TSV"
  run_ratchet
  [ "$status" -eq 2 ]
}

@test "clean improving series reports ok and zero regressions" {
  hdr; row a 50 0.00; row a 40 0.00; row b 10 0.00; row b 9 0.00
  run_ratchet
  [ "$status" -eq 0 ]
  [[ "$output" == *"REGRESSIONS 0"* ]]
}
