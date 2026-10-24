#!/usr/bin/env bats
# scripts/mlflow-upgrade-drill.sh (B227 follow-on, 2026-10-24) — prove an MLflow image's DB migration on a RESTORED COPY
# of the real `mlflow` database (newest core dump) before it touches the live one. MLflow migrations are forward-only:
# a failed upgrade on the live DB is a restore, not a rollback. These pin the verdict on the drill's own output (the
# pod run itself is a live operation, recorded in runbooks/mlflow.md): PASS only when the restore was clean, the
# upgrade ran, every counted table holds the same rows after as before, and the upgraded server answers from that DB.

setup() {
  S="$BATS_TEST_DIRNAME/../mlflow-upgrade-drill.sh"
  T="$BATS_TEST_TMPDIR"
  good() {
    printf '%s\n' "dump: weyland-all-20261024.sql.gz" "extracted: 812345 lines" "restore errors: 0" \
      "alembic-before: b7e2c1a4d9f3" "counts-before: experiments=30 runs=465 endpoints=18 " \
      "image mlflow: 3.17.2" "upgrade: ok 41" "migration: b7e2c1a4d9f3 -> 75868b020152" \
      "health: OK" "endpoints: 18" \
      "alembic-after: dc11669786a5" "counts-after: experiments=30 runs=465 endpoints=18 "
  }
}

verdict() { MLFLOW_DRILL_LIB=1 bash -c ". '$S'; drill_verdict '$1'"; }

@test "a clean restore, an upgrade, equal counts and an answering server PASS" {
  good > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"PASS: b7e2c1a4d9f3 -> dc11669786a5 in 41 s; counts unchanged; server answers, 18 gateway endpoint(s)"* ]]
}

@test "a failed upgrade is exit 1, named" {
  good | sed 's/^upgrade: ok 41$/upgrade: FAILED/' > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 1 ]
  [[ "$output" == *"the upgrade did not run cleanly"* ]]
}

@test "a row count that moved is exit 1 — a migration must not change what is stored" {
  good | sed 's/^counts-after: experiments=30 runs=465/counts-after: experiments=30 runs=464/' > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 1 ]
  [[ "$output" == *"row counts changed"* ]]
}

@test "restore errors are exit 1: the copy is not the real database" {
  good | sed 's/^restore errors: 0$/restore errors: 3/' > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 1 ]
  [[ "$output" == *"the restore reported errors"* ]]
}

@test "a missing table is exit 1" {
  good | sed 's/endpoints=18 $/endpoints=MISSING /' > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 1 ]
  [[ "$output" == *"a counted table is missing"* ]]
}

@test "a server that does not answer, or lists no endpoints, is exit 1" {
  good | sed 's/^health: OK$/health: URLError/' > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 1 ]
  [[ "$output" == *"the upgraded server did not answer /health"* ]]
  good | sed 's/^endpoints: 18$/endpoints: 0/' > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 1 ]
  [[ "$output" == *"no gateway endpoints"* ]]
}

@test "an empty log is exit 2 — nothing ran, never a pass" {
  : > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 2 ]
  [[ "$output" == *"NOT A PASS"* ]]
}

@test "the image argument is required and validated" {
  run bash "$S"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: "*"mlflow-upgrade-drill.sh <image>"* ]]
  run bash "$S" 'bad image;rm'
  [ "$status" -eq 2 ]
  [[ "$output" == *"not an image reference"* ]]
}
