#!/usr/bin/env bats
# emdash-conveyor-watch.sh (B179, 2026-10-12): the freshness signal for the software-factory conveyor. The Emdash
# automation `agent-ready-nightly` runs at 04:00 only while the app is running (no app, no run; a missed slot starts on
# the next launch), so its silence is the failure to catch. Daily at 06:00 this reads Emdash's own run records
# (read-only) and pushes a Kuma heartbeat. Fixture databases mirror the shape OBSERVED in emdash4-automations.db
# (automation_deployments.payload {name, enabled}; automation_runs.payload {status, startedAt, error}, ms epochs).
# A fixed clock (EMDASH_WATCH_NOW) keeps the age arithmetic deterministic. curl is stubbed; the assertions are on the
# verdict and what is pushed. Fail closed: a missing or unreadable store is never "fresh".

setup() {
  load helper
  setup_stubs
  W="$REPO_ROOT/scripts/emdash-conveyor-watch.sh"
  DBD="$(mktemp -d)"
  export EMDASH_AUTOMATIONS_DB="$DBD/emdash4-automations.db" KUMA_CONVEYOR_PUSH_URL="http://kuma.test/api/push/xyz"
  export EMDASH_WATCH_NO_ENV=1
  export EMDASH_WATCH_NOW=1791900000000          # a fixed "now" (ms)
}
teardown() { teardown_stubs; rm -rf "$DBD"; }

# mkdb <enabled true|false> [<run startedAt offset in hours before now> ...]   (offset "none" = a run never started)
mkdb() {
  python3 - "$EMDASH_AUTOMATIONS_DB" "$EMDASH_WATCH_NOW" "$@" <<'PY'
import sqlite3, json, sys
db, now, enabled, *runs = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "true", *sys.argv[4:]
c = sqlite3.connect(db)
c.execute("create table automation_deployments (automation_id text, enabled int, payload text, deployed_at int)")
c.execute("create table automation_runs (id text, seq int, automation_id text, status text, scheduled_at int, deadline_at int, payload text)")
c.execute("insert into automation_deployments values ('a1', ?, ?, 0)",
          (int(enabled), json.dumps({"automationId": "a1", "name": "agent-ready-nightly", "enabled": enabled})))
for i, off in enumerate(runs):
    started = None if off == "none" else now - int(float(off) * 3600 * 1000)
    status = "scheduled" if started is None else "done"
    c.execute("insert into automation_runs values (?, ?, 'a1', ?, 0, 0, ?)",
              (f"r{i}", i, status, json.dumps({"status": status, "startedAt": started, "error": None})))
c.commit()
PY
}

@test "a run started within 26 h -> exit 0 and Kuma up" {
  mkdb true 50 2; stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  called_with curl 'status=up'
  [[ "$output" == *"last run started 2.0 h ago"* ]] || { echo "$output"; return 1; }
}

@test "no run for 27 h (Emdash not running) -> exit 1 and Kuma down, naming the cause" {
  mkdb true 27 none; stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  called_with curl 'status=down'
  [[ "$output" == *"no run started in the last 26 h"* ]] || { echo "$output"; return 1; }
}

@test "the automation is disabled -> exit 1 and Kuma down, even with a recent run" {
  mkdb false 1; stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  called_with curl 'status=down'
  [[ "$output" == *"disabled"* ]] || { echo "$output"; return 1; }
}

@test "no Emdash database -> exit 2 and Kuma down (an unread store is not a fresh one)" {
  stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  called_with curl 'status=down'
  [[ "$output" == *"could not read"* ]] || { echo "$output"; return 1; }
}

@test "the automation is missing from the database -> exit 2" {
  python3 -c "import sqlite3; c=sqlite3.connect('$EMDASH_AUTOMATIONS_DB'); c.execute('create table automation_deployments (automation_id text, enabled int, payload text, deployed_at int)'); c.execute('create table automation_runs (id text, seq int, automation_id text, status text, scheduled_at int, deadline_at int, payload text)'); c.commit()"
  stub curl 0 ''
  run bash "$W"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"agent-ready-nightly not found"* ]] || { echo "$output"; return 1; }
}

@test "the database is opened read-only — the watch never writes Emdash's store" {
  mkdb true 2; stub curl 0 ''
  before="$(sha256sum "$EMDASH_AUTOMATIONS_DB")"
  run bash "$W"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(sha256sum "$EMDASH_AUTOMATIONS_DB")" = "$before" ]
}

@test "no Kuma URL -> the verdict still exits, and says it was not reported" {
  mkdb true 2; unset KUMA_CONVEYOR_PUSH_URL
  run bash "$W"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"NOT reported to Kuma"* ]] || { echo "$output"; return 1; }
}
