#!/usr/bin/env bats
# scripts/ci/golden-integration.sh — the golden paths' integration tier runner (B260). It runs each path's integration/
# tests against REAL backends (CI sidecars). These pin its decisions: an unknown ecosystem, a backend that never answers
# and a run with nothing to test are each exit 2 (never a pass), and a failing path is exit 1 with its name.

setup() {
  RUNNER="$BATS_TEST_DIRNAME/../ci/golden-integration.sh"
  SANDBOX="$(mktemp -d)"; STUB_LOG="$SANDBOX/stub.log"; mkdir -p "$SANDBOX/bin"; : > "$STUB_LOG"
  export PATH="$SANDBOX/bin:$PATH" STUB_LOG
  mkdir -p "$SANDBOX/golden-paths/python/fw/integration"
  : > "$SANDBOX/golden-paths/python/fw/integration/test_backends.py"
  : > "$SANDBOX/golden-paths/python/fw/requirements-integration.txt"
  PORT=$(( 20000 + RANDOM % 20000 ))
  python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
  LISTENER=$!
  for _ in $(seq 1 50); do (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null && break; sleep 0.1; done
  export GOLDEN_DATABASE_URL="postgresql://u:p@127.0.0.1:$PORT/db" GOLDEN_VALKEY_URL="redis://127.0.0.1:$PORT/0"
  export GOLDEN_KAFKA_BOOTSTRAP="127.0.0.1:$PORT" GOLDEN_S3_ENDPOINT="http://127.0.0.1:$PORT"
  export GOLDEN_PATHS_ROOT="$SANDBOX/golden-paths" INTEGRATION_WAIT_S=3 LANG_JUNIT_DIR="$SANDBOX/junit"
}

teardown() {
  kill "$LISTENER" 2>/dev/null || true
  rm -rf "$SANDBOX"
}

stub() { # stub <cmd> <exit> <output>
  printf '#!/usr/bin/env bash\necho "%s $*" >> "%s"\necho "%s"\nexit %s\n' "$1" "$STUB_LOG" "$3" "$2" > "$SANDBOX/bin/$1"
  chmod +x "$SANDBOX/bin/$1"
}

@test "an unknown ecosystem is exit 2, named" {
  run bash "$RUNNER" cobol
  [ "$status" -eq 2 ]
  [[ "$output" == *"cobol"* ]]
}

@test "no path with integration tests is exit 2: verifying nothing is not a pass" {
  rm -rf "$SANDBOX/golden-paths/python/fw/integration"
  stub pip 0 ok; stub pytest 0 "1 passed"
  run bash "$RUNNER" python
  [ "$status" -eq 2 ]
  [[ "$output" == *"no integration tests"* ]]
}

@test "a backend that never answers is exit 2 and named, before any test runs" {
  export GOLDEN_VALKEY_URL="redis://127.0.0.1:1/0"
  stub pip 0 ok; stub pytest 0 "1 passed"
  run bash "$RUNNER" python
  [ "$status" -eq 2 ]
  [[ "$output" == *"valkey"* && "$output" == *"unreachable"* ]]
  ! grep -q '^pytest' "$STUB_LOG"
}

@test "each path's integration tests run with its clients installed and a JUnit report" {
  stub pip 0 ok; stub pytest 0 "5 passed"
  run bash "$RUNNER" python
  [ "$status" -eq 0 ]
  grep -qE '^pip .*requirements-integration\.txt' "$STUB_LOG"
  grep -qE "^pytest .*integration .*--junitxml=$SANDBOX/junit/golden-integration-python-fw\.xml" "$STUB_LOG"
}

@test "a failing path is exit 1 and named" {
  stub pip 0 ok; stub pytest 1 "1 failed"
  run bash "$RUNNER" python
  [ "$status" -eq 1 ]
  [[ "$output" == *"python/fw"* && "$output" == *"FAILED"* ]]
}
