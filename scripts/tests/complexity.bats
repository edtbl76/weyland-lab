#!/usr/bin/env bats
# B162 — check-complexity.sh decision logic: advisory vs gate vs fail-closed.
#
# The reading (lizard + tree-sitter) and the gate DECISION are the engine's, exercised by
# test_complexity_triage.py. This file tests only the WRAPPER: it threads `--gate` to the engine and
# PROPAGATES the engine's exit (0 = clean/advisory, 1 = gate blocked, 2 = broken), failing closed when the
# engine never produced its summary line. Engine stubbed (COMPLEXITY_ENGINE) so these run without the deps.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-complexity.sh"
}

teardown() { teardown_stubs; }

# A fixed-output engine stub: prints $1, exits $2.
_engine() {
  cat > "$STUB_DIR/engine" <<EOF
#!/usr/bin/env bash
printf '%s\n' "$1"
exit ${2:-0}
EOF
  chmod +x "$STUB_DIR/engine"
  export COMPLEXITY_ENGINE="$STUB_DIR/engine"
}

# A gate-aware stub: prints a valid summary line, exits 1 IFF it was passed --gate (else 0) — proving the
# wrapper threads the flag and propagates the engine's decision.
_engine_gate_aware() {
  cat > "$STUB_DIR/engine" <<'EOF'
#!/usr/bin/env bash
echo "complexity triage: 1 TANGLED, 0 SHALLOW, 0 OUTLIER-REVIEW, 0 DEEP"
for a in "$@"; do [ "$a" = "--gate" ] && exit 1; done
exit 0
EOF
  chmod +x "$STUB_DIR/engine"
  export COMPLEXITY_ENGINE="$STUB_DIR/engine"
}

@test "the guard exists" {
  [ -f "$GUARD" ]
}

@test "advisory (default): prints findings and exits 0 (engine advisory always exits 0)" {
  _engine "complexity triage: 3 TANGLED, 0 SHALLOW, 0 OUTLIER-REVIEW, 0 DEEP (advisory)
  TANGLED        high   foo.py:10  bar" 0
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"TANGLED"* ]]
}

@test "advisory mode never invents a gate even when the engine reports TANGLED/SHALLOW" {
  # The engine in advisory mode ALWAYS exits 0; the wrapper must propagate that, not gate on the text.
  _engine "complexity triage: 5 TANGLED, 2 SHALLOW, 0 OUTLIER-REVIEW, 0 DEEP (advisory)
  TANGLED        high   a.py:1  x
  SHALLOW        medium b.py:1  y" 0
  run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "--gate propagates the engine's exit 1 (blocking findings)" {
  _engine "complexity triage: 1 TANGLED, 0 SHALLOW, 0 OUTLIER-REVIEW, 0 DEEP (gated)
  TANGLED        high   foo.py:10  bar

GATE FAILED: 1 blocking finding(s)" 1
  run bash "$GUARD" --gate
  [ "$status" -eq 1 ]
  [[ "$output" == *"GATE FAILED"* ]]
}

@test "--gate passes (exit 0) when the engine exits 0 (nothing blocks)" {
  _engine "complexity triage: 0 TANGLED, 0 SHALLOW, 2 OUTLIER-REVIEW, 1 DEEP (gated)
  OUTLIER_REVIEW medium foo.py:5  baz" 0
  run bash "$GUARD" --gate
  [ "$status" -eq 0 ]
}

@test "the wrapper threads --gate to the engine and only gates when asked" {
  _engine_gate_aware
  run bash "$GUARD" --gate      # engine sees --gate -> exit 1 -> wrapper exit 1
  [ "$status" -eq 1 ]
  run bash "$GUARD"             # no --gate -> engine exit 0 -> wrapper exit 0
  [ "$status" -eq 0 ]
}

@test "a crashed engine (no summary line) is exit 2 — fail closed, never a silent pass" {
  _engine "ModuleNotFoundError: No module named 'lizard'" 1
  run bash "$GUARD" --gate
  [ "$status" -eq 2 ]
  [[ "$output" == *"could not run"* ]]
}
