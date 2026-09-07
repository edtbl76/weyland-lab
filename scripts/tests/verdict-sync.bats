#!/usr/bin/env bats
# Tests for check-verdict-sync.sh (B152 architecture guard). Proves the fail-closed exit contract by
# REASON, not just exit sign: 0 identical · 1 differ · 2 cannot-run. Uses fixtures via VERDICT_A/VERDICT_B.

setup() {
  GUARD="${BATS_TEST_DIRNAME}/../check-verdict-sync.sh"
  TMP="$(mktemp -d)"
}
teardown() { rm -rf "$TMP"; }

@test "identical copies pass with exit 0" {
  printf 'same\n' > "$TMP/a.py"; printf 'same\n' > "$TMP/b.py"
  run env VERDICT_A="$TMP/a.py" VERDICT_B="$TMP/b.py" bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"byte-identical"* ]]
}

@test "drift fails with exit 1 and shows the diff reason" {
  printf 'one\n' > "$TMP/a.py"; printf 'two\n' > "$TMP/b.py"
  run env VERDICT_A="$TMP/a.py" VERDICT_B="$TMP/b.py" bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"DRIFT"* ]]
}

@test "a missing file is CANNOT-RUN exit 2, never a false pass" {
  printf 'same\n' > "$TMP/a.py"
  run env VERDICT_A="$TMP/a.py" VERDICT_B="$TMP/does-not-exist.py" bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT RUN"* ]]
}

@test "the real repo copies are in sync (the live invariant)" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
}
