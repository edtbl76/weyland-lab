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
      "health: OK" "endpoints: 18" "chat: ok ollama-qwen25-7b answered" \
      "alembic-after: dc11669786a5" "counts-after: experiments=30 runs=465 endpoints=18 "
  }
}

verdict() { MLFLOW_DRILL_LIB=1 bash -c ". '$S'; drill_verdict '$1'"; }

@test "a clean restore, an upgrade, equal counts and an answering server PASS" {
  good > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"PASS: b7e2c1a4d9f3 -> dc11669786a5 in 41 s; counts unchanged; server answers, 18 gateway endpoint(s); a real gateway chat answered"* ]]
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

# 2026-10-24, the drill's first real run: 3.17.2 ships SQLAlchemy 2.1, which maps a bare postgresql:// to the psycopg
# (v3) driver; the image has psycopg2, so `db upgrade` failed. The live command used a bare postgresql:// too, so the
# drill must use the LIVE command's scheme, read from the manifest, or it proves a URI production never runs.
scheme() { MLFLOW_DRILL_LIB=1 bash -c ". '$S'; db_scheme '$1'"; }

@test "the drill takes the database URI scheme from the live manifest" {
  printf '      mlflow db upgrade "postgresql+psycopg2://$(U)@db:5432/mlflow" &&\n      --backend-store-uri "postgresql+psycopg2://$(U)@db:5432/mlflow"\n' > "$T/m.yaml"
  run scheme "$T/m.yaml"
  [ "$status" -eq 0 ]
  [ "$output" = "postgresql+psycopg2" ]
  printf '      mlflow db upgrade "postgresql://$(U)@db:5432/mlflow"\n' > "$T/bare.yaml"
  run scheme "$T/bare.yaml"
  [ "$output" = "postgresql" ]              # carried as-is: the drill then fails where production would
}

@test "two different schemes in the manifest, or none, is exit 2: no guessing" {
  printf 'a "postgresql://x/mlflow"\nb "postgresql+psycopg2://x/mlflow"\n' > "$T/m.yaml"
  run scheme "$T/m.yaml"
  [ "$status" -eq 2 ]
  [[ "$output" == *"not exactly one"* ]]
  printf 'nothing here\n' > "$T/none.yaml"
  run scheme "$T/none.yaml"
  [ "$status" -eq 2 ]
}

@test "a pod that ran and failed is judged on its output (exit 1, named), not 'could not run'" {
  good | sed 's/^upgrade: ok 41$/upgrade: FAILED/' > "$T/log"
  run env MLFLOW_DRILL_LIB=1 bash -c ". '$S'; judge Failed '$T/log'"
  [ "$status" -eq 1 ]
  [[ "$output" == *"the upgrade did not run cleanly"* ]]
  : > "$T/empty"
  run env MLFLOW_DRILL_LIB=1 bash -c ". '$S'; judge Failed '$T/empty'"
  [ "$status" -eq 2 ]
  run env MLFLOW_DRILL_LIB=1 bash -c ". '$S'; judge Pending '$T/log'"
  [ "$status" -eq 2 ]
  [[ "$output" == *"phase 'Pending'"* ]]
}

# 2026-10-25: the drill PASSED 3.17.2 and production's gateway then failed every call: the drill ran its own server
# config (one worker, no gateway env) and never sent a request. It now runs the LIVE container's env values and worker
# count, read from the manifest, and its verdict needs a real chat answer through the gateway.
@test "the drill reads the live container's literal env values and worker count from the manifest" {
  printf '%s\n' 'kind: Deployment' 'spec:' '  template:' '    spec:' '      containers:' '        - name: mlflow' \
    '          args:' '            - >' '              mlflow server --host 0.0.0.0 --port 5000 --workers 2' \
    '          env:' '            - name: MLFLOW_GATEWAY_URI' '              value: http://localhost:5000' \
    '            - name: POSTGRES_PASSWORD' '              valueFrom:' '                secretKeyRef: {name: s, key: k}' \
    '            - name: MLFLOW_GATEWAY_API_BASE_ALLOW_PRIVATE_IPS' '              value: "true"' > "$T/m.yaml"
  run env MLFLOW_DRILL_LIB=1 bash -c ". '$S'; manifest_env '$T/m.yaml'"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"MLFLOW_GATEWAY_URI=http://localhost:5000"* ]]
  [[ "$output" == *"MLFLOW_GATEWAY_API_BASE_ALLOW_PRIVATE_IPS=true"* ]]
  [[ "$output" != *"POSTGRES_PASSWORD"* ]]                     # secret-sourced entries are never copied
  run env MLFLOW_DRILL_LIB=1 bash -c ". '$S'; manifest_workers '$T/m.yaml'"
  [ "$output" = "2" ]
}

@test "a drill whose gateway chat failed is exit 1, even with a clean upgrade" {
  good | sed 's/^chat: ok .*/chat: FAILED HTTP 502/' > "$T/log"
  run verdict "$T/log"
  [ "$status" -eq 1 ]
  [[ "$output" == *"the gateway did not answer a real chat request"* ]]
}

@test "the image argument is required and validated" {
  run bash "$S"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: "*"mlflow-upgrade-drill.sh <image>"* ]]
  run bash "$S" 'bad image;rm'
  [ "$status" -eq 2 ]
  [[ "$output" == *"not an image reference"* ]]
}
