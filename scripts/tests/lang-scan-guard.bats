#!/usr/bin/env bats
#
# run-lang-scan.sh — the SCAN lane's "missing scanner" guard MUST fail closed.
#
# Two fail-open bugs this suite pins (found during the B153 golden-paths-as-fixtures work):
#
#   1. run_tool matched only the OLD npm strings (`could not determine executable`,
#      `npm ERR! canceled`). Current npm (11) prints
#      `npm error npx canceled due to missing packages and no YES option`, which slipped through and
#      read as an rc=1 FINDING rather than LANE BROKEN — a missing eslint on a golden path sat green.
#
#   2. scan_node/scan_rust/scan_java run their tools with no `set -e` and returned only the LAST
#      run_tool's status, so a missing scanner EARLIER in the sequence was masked by a later one that
#      resolved. The negative case below breaks eslint (not the last tool) while license-checker
#      resolves — pre-fix that returned 0 (green); it must now exit 2.
#
# Same class as the five silent-failure defects in project.md: an absent result must never stand for
# success. Asserts on the LANE BROKEN reason, never just a non-zero status.

load helper

setup() {
  setup_stubs
  SCAN="$REPO_ROOT/scripts/run-lang-scan.sh"
  SANDBOX="$(mktemp -d)"; export SANDBOX
  mkdir -p "$SANDBOX/fix/javascript/node_modules" "$SANDBOX/empty"
  printf '{"name":"fixture"}\n' > "$SANDBOX/fix/javascript/package.json"
  : > "$SANDBOX/fix/javascript/hello.test.js"
  # npm (install/audit) always succeeds; node_modules already present so install is skipped anyway.
  stub npm 0 ""
}

teardown() {
  teardown_stubs
  [ -n "${SANDBOX:-}" ] && [ -d "$SANDBOX" ] && rm -rf "$SANDBOX"
  return 0
}

# A custom npx stub (the `stub` helper answers every call identically; we need it to differ by tool).
write_npx() {
  cat > "$STUB_DIR/npx" <<'NPX_EOF'
#!/usr/bin/env bash
case "$*" in
  *eslint*)          echo 'npm error npx canceled due to missing packages and no YES option: ["eslint@9"]'; exit 1 ;;
  *license-checker*) echo 'clean'; exit 0 ;;
  *)                 echo 'ok'; exit 0 ;;
esac
NPX_EOF
  chmod +x "$STUB_DIR/npx"
}

@test "a scanner npx cannot resolve (CURRENT npm message) fails the lane CLOSED, not as a finding" {
  write_npx
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/empty" \
      bash "$SCAN" javascript
  [ "$status" -eq 2 ]
  [[ "$output" == *"LANE BROKEN"* ]]
  [[ "$output" == *"eslint"* ]]
}

@test "a broken scanner that is NOT the last tool still fails the lane (scan_node aggregates)" {
  # eslint breaks, but license-checker (invoked AFTER it) resolves. Before aggregation the lane read
  # license-checker's exit 0 and went green; it must now propagate the earlier break.
  write_npx
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/empty" \
      bash "$SCAN" javascript
  [ "$status" -eq 2 ]
}

@test "when every scanner resolves, the lane is green (the guard does not over-fail)" {
  # npx resolves everything cleanly.
  cat > "$STUB_DIR/npx" <<'NPX_EOF'
#!/usr/bin/env bash
echo 'ok'; exit 0
NPX_EOF
  chmod +x "$STUB_DIR/npx"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/empty" \
      bash "$SCAN" javascript
  [ "$status" -eq 0 ]
  [[ "$output" == *"scanners ran"* ]]
}
