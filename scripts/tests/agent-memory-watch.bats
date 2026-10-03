#!/usr/bin/env bats
# agent-memory-watch.sh (B182, 2026-10-03) — every 15 min: gitleaks over the shared notes + a read-only health check of
# the store, reported to a Kuma push monitor. Basic Memory itself ACCEPTS a token-shaped note (verified), so this is the
# "flagged" half of B182's "a write containing a token-shaped string is rejected or flagged".
# The scanner, the health check and curl are stubbed; the assertions are on the VERDICT (exit code + what is pushed).
# Fail closed: a scanner that could not run, or a store that does not answer, is never reported as clean.

setup() {
  load helper
  setup_stubs
  W="$REPO_ROOT/scripts/agent-memory-watch.sh"
  MEM="$(mktemp -d)"
  export AGENT_MEMORY_DIR="$MEM" KUMA_MEMORY_PUSH_URL="http://kuma.test/api/push/abc" AGENT_MEMORY_NO_ENV=1
  export CHECK_CMD="$STUB_DIR/healthcheck"
}
teardown() { teardown_stubs; rm -rf "$MEM"; }

clean_scan()   { stub docker 0 'INF no leaks found'; }
healthy()      { printf '#!/usr/bin/env bash\necho "OK — read-only"; exit 0\n' > "$STUB_DIR/healthcheck"; chmod +x "$STUB_DIR/healthcheck"; }
health_exit()  { printf '#!/usr/bin/env bash\necho "%s" >&2; exit %s\n' "$2" "$1" > "$STUB_DIR/healthcheck"; chmod +x "$STUB_DIR/healthcheck"; }

@test "clean notes + a healthy store -> exit 0 and Kuma up" {
  clean_scan; healthy; stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  called_with curl 'status=up'
}

@test "a secret in the notes -> exit 1, Kuma down naming it a secret, and the value is never printed" {
  stub docker 1 'WRN leaks found: 1'; healthy; stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  called_with curl 'status=down'
  [[ "$output" == *"secret"* ]] || { echo "$output"; return 1; }
  called_with docker '--redact'        # gitleaks must redact what it prints
}

@test "the store does not answer -> exit 2 and Kuma down (unreachable is not 'no memory')" {
  clean_scan; health_exit 2 'UNREACHABLE'; stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  called_with curl 'status=down'
  [[ "$output" == *"unreachable"* ]] || { echo "$output"; return 1; }
}

@test "the store answers but its index is incomplete -> exit 1 and Kuma down" {
  clean_scan; health_exit 1 'indexed FAIL'; stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  called_with curl 'status=down'
}

@test "the scanner itself fails to run -> exit 2, Kuma down — an unscanned directory is not a clean one" {
  stub docker 125 'docker: Error response from daemon'; healthy; stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  called_with curl 'status=down'
  [[ "$output" == *"could not scan"* ]] || { echo "$output"; return 1; }
}

@test "no Kuma URL -> the verdict still stands and the gap is said out loud" {
  clean_scan; healthy; stub curl 0 ''
  KUMA_MEMORY_PUSH_URL="" run bash "$W"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  never_called curl
  [[ "$output" == *"KUMA_MEMORY_PUSH_URL unset"* ]] || { echo "$output"; return 1; }
}

@test "a missing notes directory -> exit 2 (cannot check), never a clean scan" {
  clean_scan; healthy; stub curl 0 ''
  AGENT_MEMORY_DIR="$MEM/does-not-exist" run bash "$W"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  called_with curl 'status=down'
}
