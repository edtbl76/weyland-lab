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

# 2026-10-13 (owner): catalog-only drift is UP. It pushed down every night 10-05..10-12 while PR #130 waited — a red light
# that meant "a PR is open" (any `docker pull` re-tripped it). The PR is where drift is curated; Kuma pages on failures.
@test "decide_signal: catalog drift only => up, naming the change and the open PR" {
  run decide_signal 1 "" "+3/-1 lines"
  [[ "$output" == up* ]]
  [[ "$output" == *"catalog drift +3/-1 lines → inventory PR open for review"* ]]
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

# B180: the host placement check (placement_check.py --hosts) rides the same heartbeat. 4th arg = its exit code.
@test "decide_signal: catalog clean but placement host drift (rc 1) => down naming placement" {
  run decide_signal 0 "" "none" 1
  [[ "$output" == down* ]]
  [[ "$output" == *"placement: host drift"* ]]
}

@test "decide_signal: placement check could not read (rc 2) => down, never a false up" {
  run decide_signal 0 "" "none" 2
  [[ "$output" == down* ]]
  [[ "$output" == *"placement: host check could not read"* ]]
}

@test "decide_signal: catalog drift AND placement drift => down naming both" {
  run decide_signal 1 "" "+2/-0 lines" 1
  [[ "$output" == down* ]]
  [[ "$output" == *"catalog drift +2/-0 lines"* ]]
  [[ "$output" == *"placement: host drift"* ]]
}

@test "decide_signal: placement clean (rc 0) keeps up" {
  run decide_signal 0 "" "none" 0
  [[ "$output" == up*"clean, all hosts reachable"* ]]
}

@test "decide_signal: a placement rc that is not 0/1/2 is down, not up (fail closed)" {
  run decide_signal 0 "" "none" 127
  [[ "$output" == down* ]]
  [[ "$output" == *"placement: host check exited 127"* ]]
}

# The Port emit + read-back verify (B169) used to be reported only on stdout, so a verify failing every night never
# reached Kuma (found 2026-09-30). 5th arg = 1 when emit/verify failed.
@test "decide_signal: Port emit/verify failed => down, even when everything else is clean" {
  run decide_signal 0 "" "none" 0 1
  [[ "$output" == down* ]]
  [[ "$output" == *"port: emit/verify failed"* ]]
}

@test "decide_signal: Port ok (0) keeps up" {
  run decide_signal 0 "" "none" 0 0
  [[ "$output" == up* ]]
}

# 2026-10-13: the Kuma push-interval guard (kuma_push_check.py) rides the same heartbeat. 6th arg = its exit code.
# emdash-conveyor sat at Kuma's 60 s default (red a minute after every daily push) with nothing checking it.
@test "decide_signal: a push-monitor interval finding (rc 1) => down naming it" {
  run decide_signal 0 "" "none" 0 0 1
  [[ "$output" == down* ]]
  [[ "$output" == *"kuma: push-monitor interval mismatch"* ]]
}

@test "decide_signal: the interval guard could not read Kuma (rc 2) => down, never a false up" {
  run decide_signal 0 "" "none" 0 0 2
  [[ "$output" == down* ]]
  [[ "$output" == *"kuma: interval check could not read"* ]]
}

@test "decide_signal: catalog drift with an interval finding => down naming both" {
  run decide_signal 1 "" "+3/-0 lines" 0 0 1
  [[ "$output" == down* ]]
  [[ "$output" == *"catalog drift +3/-0 lines"* ]]
  [[ "$output" == *"kuma: push-monitor interval mismatch"* ]]
}

@test "decide_signal: interval guard clean (0) keeps up" {
  run decide_signal 0 "" "none" 0 0 0
  [[ "$output" == up*"clean, all hosts reachable"* ]]
}

# sync_port (2026-10-26): Port is synced from the COMMITTED catalog (the origin/main worktree), never the live checkout.
# The live one moved under a run that day: emit read the pre-merge file, a `git pull` landed, verify read the merged one
# (Port 925 vs SoT 921, heartbeat down). It would also publish uncommitted edits to Port as if accepted.
sync_stub() { # sync_stub <verify-rc> — an INV_CMD that logs "<verb> <MACHINE_INV_SOT>" and fails verify with <rc>
  export SYNC_LOG="$BATS_TEST_TMPDIR/inv.log" SYNC_VERIFY_RC="$1"
  printf '#!/usr/bin/env bash\necho "$1 ${MACHINE_INV_SOT:-unset}" >> "$SYNC_LOG"\n[ "$1" = verify ] && exit "$SYNC_VERIFY_RC"\nexit 0\n' \
    > "$BATS_TEST_TMPDIR/inv"
  chmod +x "$BATS_TEST_TMPDIR/inv"
  INV_CMD="$BATS_TEST_TMPDIR/inv"
  PORT_ENV="$BATS_TEST_TMPDIR/port.env"; : > "$PORT_ENV"
}

@test "sync_port: emits AND verifies the catalog it is given (the origin/main worktree), not the live checkout" {
  sync_stub 0
  run sync_port "/wt/machine-inventory.yaml"
  [ "$status" -eq 0 ]
  grep -qx 'emit /wt/machine-inventory.yaml' "$SYNC_LOG"
  grep -qx 'verify /wt/machine-inventory.yaml' "$SYNC_LOG"
  ! grep -q 'unset' "$SYNC_LOG"
}

@test "sync_port: a failed read-back verify is a failure, never a pass" {
  sync_stub 1
  run sync_port "/wt/machine-inventory.yaml"
  [ "$status" -ne 0 ]
  grep -qx 'verify /wt/machine-inventory.yaml' "$SYNC_LOG"   # it got as far as verifying: the failure is verify's
}

@test "sync_port: a missing Port env is a failure (nothing was synced)" {
  sync_stub 0
  PORT_ENV="$BATS_TEST_TMPDIR/absent.env"
  run sync_port "/wt/machine-inventory.yaml"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Port not synced"* ]]
  [ ! -s "$SYNC_LOG" ]
}
