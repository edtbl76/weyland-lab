#!/usr/bin/env bats
# scripts/pg-restore-drill.sh (2026-10-21) — the core Postgres dump's non-destructive restore drill. These pin its
# decisions with a stub kubectl (the pod's phase and log come from env): what it refuses, and that only a Succeeded pod
# whose log says "restore errors: 0" with every table present is a pass. The real drill RUN is in docs/dr.md.

setup() {
  T="$BATS_TEST_TMPDIR"; mkdir -p "$T/bin"
  SCRIPT="$BATS_TEST_DIRNAME/../pg-restore-drill.sh"
  cat > "$T/bin/kubectl" <<'SH'
#!/bin/sh
case "$*" in
  *"get pod"*"jsonpath"*) printf '%s' "${STUB_PHASE:-Succeeded}";;
  *" logs "*) printf '%b' "${STUB_LOG:-}";;
esac
exit 0
SH
  chmod +x "$T/bin/kubectl"
  # no real waiting in tests
  printf '#!/bin/sh\nexit 0\n' > "$T/bin/sleep"; chmod +x "$T/bin/sleep"
  export PATH="$T/bin:$PATH"
}

@test "no table names is a usage error, exit 2" {
  run bash "$SCRIPT" mlflow
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage:"* ]]
}

@test "a database name with anything but [a-z0-9_] is refused, exit 2" {
  run bash "$SCRIPT" 'x"; drop' runs
  [ "$status" -eq 2 ]
  [[ "$output" == *"database name must be"* ]]
}

@test "a clean restore with every table counted is a pass" {
  STUB_LOG='dump: weyland-all-20261021.sql.gz\nextracted: 10 lines\nrestore errors: 0\nruns=465 \n' run bash "$SCRIPT" mlflow runs
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"restore OK"* ]]
}

@test "restore errors are exit 1, never a pass" {
  STUB_LOG='restore errors: 3\nERROR: relation x\nruns=0 \n' run bash "$SCRIPT" mlflow runs
  [ "$status" -eq 1 ]
  [[ "$output" == *"RESTORE PROBLEM"* ]]
}

@test "a table missing from the restored copy is exit 1" {
  STUB_LOG='restore errors: 0\nruns=MISSING \n' run bash "$SCRIPT" mlflow runs
  [ "$status" -eq 1 ]
}

@test "a pod that failed is exit 2 (the drill did not run), named" {
  STUB_PHASE=Failed STUB_LOG='restore errors: 0\n' run bash "$SCRIPT" mlflow runs
  [ "$status" -eq 2 ]
  [[ "$output" == *"phase 'Failed'"* ]]
}

@test "an empty log is exit 2, never a clean pass over nothing" {
  STUB_LOG='' run bash "$SCRIPT" mlflow runs
  [ "$status" -eq 2 ]
  [[ "$output" == *"printed nothing"* ]]
}
