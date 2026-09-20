#!/usr/bin/env bats
# Tests for machine-inv-drift.sh (B170). The git/gh/ssh plumbing is env-dependent (validated by a live
# dry-run, per the "observe the real thing" rule), so these pin the one piece that MAKES A DECISION with no
# I/O: decide_signal — the Kuma/Telegram state, which must be `up` ONLY when the catalog is clean AND every
# host was reachable. The lib seam (MACHINE_INV_DRIFT_LIB=1) sources the functions without running main.

setup() {
  export MACHINE_INV_DRIFT_LIB=1
  # shellcheck disable=SC1090
  . "${BATS_TEST_DIRNAME}/../machine-inv-drift.sh"
}

@test "decide_signal: clean + all reachable => up" {
  run decide_signal 0 "" "none"
  [[ "$output" == up*"clean, all hosts reachable"* ]]
}

@test "decide_signal: drift only => down naming the change" {
  run decide_signal 1 "" "+3/-1 lines"
  [[ "$output" == down* ]]
  [[ "$output" == *"drift: +3/-1 lines"* ]]
}

@test "decide_signal: a host unreachable (no drift) => down, never a false up" {
  run decide_signal 0 " weyland" "none"
  [[ "$output" == down* ]]
  [[ "$output" == *"unreachable: weyland"* ]]
}

@test "decide_signal: drift AND unreachable => down naming both" {
  run decide_signal 1 " weyland" "+1/-0 lines"
  [[ "$output" == down* ]]
  [[ "$output" == *"drift"* ]]
  [[ "$output" == *"unreachable: weyland"* ]]
}
