#!/usr/bin/env bats
# Tests for scripts/issue-time.sh (B185) — the one command for time per Linear issue: fetch the newest B194 Linear
# snapshot, then run issue_time_report.py (table · --json · --port). `mc ls` output OBSERVED 2026-10-13:
#   [2026-10-13 09:59:46 EDT]     0B 2026-10-13T092012Z/
# mc and the report are stubbed through the script's seams; what is pinned is the script's own decisions.

setup() {
  STUB="$BATS_TEST_TMPDIR/stub"; mkdir -p "$STUB"
  export ISSUE_TIME_CACHE="$BATS_TEST_TMPDIR/cache"
  export ISSUE_TIME_SESSIONS="$BATS_TEST_TMPDIR/sessions"
  export ISSUE_TIME_PORT_ENV="$BATS_TEST_TMPDIR/port.env"
  export ISSUE_TIME_OWNER="$BATS_TEST_TMPDIR/owner_time.json"
  export MC_LOG="$BATS_TEST_TMPDIR/mc.log" PY_LOG="$BATS_TEST_TMPDIR/py.log"
  cat > "$STUB/mc" <<'SH'
#!/usr/bin/env bash
echo "$*" >> "$MC_LOG"
case "$1" in
  ls) [ -n "${MC_LS_EMPTY:-}" ] || printf '[2026-10-13 09:59:46 EDT]     0B 2026-10-12T092015Z/\n[2026-10-13 09:59:46 EDT]     0B 2026-10-13T092012Z/\n' ;;
  cp) [ -n "${MC_CP_FAIL:-}" ] && exit 1; printf 'snapshot' > "${@: -1}" ;;
esac
SH
  cat > "$STUB/report" <<'SH'
#!/usr/bin/env bash
echo "$* | PORT_CLIENT_ID=${PORT_CLIENT_ID:-unset}" >> "$PY_LOG"
exit "${REPORT_RC:-0}"
SH
  chmod +x "$STUB/mc" "$STUB/report"
  export ISSUE_TIME_MC="$STUB/mc" ISSUE_TIME_REPORT="$STUB/report"
  SCRIPT="$BATS_TEST_DIRNAME/../issue-time.sh"
}

@test "fetches the NEWEST snapshot and runs the report on it" {
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  grep -q "cp -q weyland/linear-backup/snapshots/2026-10-13T092012Z/issues.json.gz $ISSUE_TIME_CACHE/linear-issues.json.gz" "$MC_LOG"
  grep -q "cp -q weyland/linear-backup/snapshots/2026-10-13T092012Z/workflowStates.json.gz $ISSUE_TIME_CACHE/linear-workflow-states.json.gz" "$MC_LOG"
  grep -q -- "--sessions $ISSUE_TIME_SESSIONS --issues $ISSUE_TIME_CACHE/linear-issues.json.gz --states $ISSUE_TIME_CACHE/linear-workflow-states.json.gz" "$PY_LOG"
}

@test "passes --json through, and reads no Port credentials for it" {
  printf 'PORT_CLIENT_ID=abc\n' > "$ISSUE_TIME_PORT_ENV"
  run bash "$SCRIPT" --json
  [ "$status" -eq 0 ]
  grep -q -- "--json | PORT_CLIENT_ID=unset" "$PY_LOG"
}

@test "--port loads the Port credentials" {
  printf 'PORT_CLIENT_ID=abc\nPORT_CLIENT_SECRET=def\n' > "$ISSUE_TIME_PORT_ENV"
  run bash "$SCRIPT" --port
  [ "$status" -eq 0 ]
  grep -q -- "--port | PORT_CLIENT_ID=abc" "$PY_LOG"
}

@test "--port without the Port env file is exit 2, before anything runs" {
  run bash "$SCRIPT" --port
  [ "$status" -eq 2 ]
  [[ "$output" == *"Port credentials"*"port.env"* ]]
  [ ! -f "$PY_LOG" ]
}

@test "no snapshot listed is exit 2, never a report on a stale or missing file" {
  MC_LS_EMPTY=1 run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no Linear snapshot"* ]]
  [ ! -f "$PY_LOG" ]
}

@test "a failed snapshot copy is exit 2 naming it" {
  MC_CP_FAIL=1 run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"could not fetch"*"2026-10-13T092012Z"* ]]
  [ ! -f "$PY_LOG" ]
}

@test "the report's exit code is the script's (1 = Port read-back mismatch)" {
  REPORT_RC=1 run bash "$SCRIPT" --json
  [ "$status" -eq 1 ]
}

@test "an unknown option is refused with exit 2" {
  run bash "$SCRIPT" --bogus
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
}

# B185 lane 2 (2026-10-15): the owner's own time (owner_time.py) joins the report when it was collected.
@test "passes the owner-time file to the report when it exists" {
  printf '{"issues": {}, "sources": {}}' > "$ISSUE_TIME_OWNER"
  run bash "$SCRIPT" --json
  [ "$status" -eq 0 ]
  grep -q -- "--owner $ISSUE_TIME_OWNER" "$PY_LOG"
}

@test "without an owner-time file the report runs without it, and says owner time was not collected" {
  run bash "$SCRIPT" --json
  [ "$status" -eq 0 ]
  ! grep -q -- "--owner" "$PY_LOG"
  [[ "$output" == *"owner time not collected"* ]]
}
