#!/usr/bin/env bats
# scripts/check-dockerfile-installs.sh (2026-10-16) — the ratchet on packages a Dockerfile installs outside a
# requirements file. The counting rules are pytest's (test_dockerfile_installs.py); these pin the wrapper's decisions:
# exit 0 at/under the ceiling (naming one below it), 1 above it or unlisted, 2 when it cannot check.

setup() {
  T="$BATS_TEST_TMPDIR"
  mkdir -p "$T/nodes/a" "$T/nodes/b"
  export DOCKERFILE_INSTALLS_ROOT="$T" DOCKERFILE_INSTALLS_BASELINE="$T/baseline"
  SCRIPT="$BATS_TEST_DIRNAME/../check-dockerfile-installs.sh"
  printf 'FROM python:3.12-slim\nRUN pip install fastapi uvicorn\n' > "$T/nodes/a/Dockerfile"
  printf 'FROM python:3.12-slim\nRUN pip install -r requirements.txt\n' > "$T/nodes/b/Dockerfile"
  printf 'nodes/a/Dockerfile\t2\n' > "$T/baseline"
}

@test "at the ceiling is exit 0" {
  run bash "$SCRIPT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"OK — 2 direct pip install(s) across 1 Dockerfile(s)"* ]]
}

@test "one more direct install is exit 1, named" {
  printf 'FROM python:3.12-slim\nRUN pip install fastapi uvicorn httpx\n' > "$T/nodes/a/Dockerfile"
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"FAIL nodes/a/Dockerfile: 3 direct pip install(s), baseline 2"* ]]
}

@test "a new Dockerfile with a direct install is exit 1" {
  mkdir -p "$T/nodes/c"; printf 'RUN pip install duckdb\n' > "$T/nodes/c/Dockerfile"
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"nodes/c/Dockerfile: 1 direct pip install(s), baseline 0 (not in the baseline)"* ]]
}

@test "fewer than the ceiling passes and asks for the baseline to be lowered" {
  printf 'FROM python:3.12-slim\nRUN pip install -r requirements.txt\n' > "$T/nodes/a/Dockerfile"
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"LOWER THE BASELINE: nodes/a/Dockerfile: 0 < baseline 2"* ]]
}

@test "no Dockerfile at all is exit 2, never a clean tree" {
  rm -rf "$T/nodes"; mkdir -p "$T/nodes"
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK: no Dockerfile"* ]]
}

@test "an unreadable baseline is exit 2" {
  printf 'not a valid row\n' > "$T/baseline"
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK: baseline"* ]]
}

@test "the real repo is at or under its committed baseline" {
  unset DOCKERFILE_INSTALLS_ROOT DOCKERFILE_INSTALLS_BASELINE
  run bash "$SCRIPT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
