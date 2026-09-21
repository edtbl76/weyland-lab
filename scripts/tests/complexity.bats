#!/usr/bin/env bats
# B162 — check-complexity.sh decision logic: advisory vs gate vs fail-closed.
#
# The engine (lizard + tree-sitter) is exercised by its own pytest suite (test_complexity_triage.py).
# Here we test only the WRAPPER's decisions, with the engine stubbed (COMPLEXITY_ENGINE) so these run
# without the analysis deps — the same "assert the DECISION, not the tool" pattern as the other guards.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-complexity.sh"
}

teardown() { teardown_stubs; }

# An engine stub: prints $STUB_OUT, exits $STUB_RC.
_engine() {
  cat > "$STUB_DIR/engine" <<EOF
#!/usr/bin/env bash
printf '%s\n' "$1"
exit ${2:-0}
EOF
  chmod +x "$STUB_DIR/engine"
  export COMPLEXITY_ENGINE="$STUB_DIR/engine"
}

@test "the guard exists" {
  # Invoked as `bash scripts/check-complexity.sh` in CI (like the sibling guards), so existence — not
  # the exec bit — is what matters.
  [ -f "$GUARD" ]
}

@test "advisory (default): prints findings and exits 0 even with TANGLED present" {
  _engine "complexity triage: 3 TANGLED, 0 SHALLOW
  TANGLED        high   foo.py:10  bar
                        ccn=30" 0
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"TANGLED"* ]]
}

@test "--gate FAILS (exit 1) when a TANGLED finding is present" {
  _engine "complexity triage: 1 TANGLED, 0 SHALLOW
  TANGLED        high   foo.py:10  bar
                        ccn=30" 0
  run bash "$GUARD" --gate
  [ "$status" -eq 1 ]
  [[ "$output" == *"GATE FAILED"* ]]
}

@test "--gate FAILS (exit 1) on a SHALLOW finding too" {
  _engine "complexity triage: 0 TANGLED, 1 SHALLOW
  SHALLOW        medium foo.py:1  <delegation:x>
                        3 sibling modules" 0
  run bash "$GUARD" --gate
  [ "$status" -eq 1 ]
}

@test "--gate PASSES (exit 0) when only OUTLIER-REVIEW/DEEP are present" {
  _engine "complexity triage: 0 TANGLED, 0 SHALLOW
  OUTLIER_REVIEW medium foo.py:5  baz
                        long and unusual
  DEEP           low    foo.py:9  qux" 0
  run bash "$GUARD" --gate
  [ "$status" -eq 0 ]
}

@test "the summary line's word TANGLED does NOT trip the gate (only finding lines do)" {
  # 'complexity triage: 5 TANGLED, ...' is a count, not a finding — it must not fail a clean --gate.
  _engine "complexity triage: 5 TANGLED, 2 SHALLOW (historical note)" 0
  run bash "$GUARD" --gate
  [ "$status" -eq 0 ]
}

@test "a failing engine is exit 2 (fail closed), never a silent pass" {
  _engine "ModuleNotFoundError: lizard" 2
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"could not run"* ]]
}
