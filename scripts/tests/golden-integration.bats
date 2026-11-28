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
  # trunk-upload.sh reads only <dir>/<source>/*.xml (CI #740: a top-level file was "no JUnit reports")
  grep -qE "^pytest .*integration .*--junitxml=$SANDBOX/junit/integration-python/python-fw\.xml" "$STUB_LOG"
  [ -d "$SANDBOX/junit/integration-python" ]
}

@test "a failing path is exit 1 and named" {
  stub pip 0 ok; stub pytest 1 "1 failed"
  run bash "$RUNNER" python
  [ "$status" -eq 1 ]
  [[ "$output" == *"python/fw"* && "$output" == *"FAILED"* ]]
}

@test "REGRESSION (CI #739): a relative LANG_JUNIT_DIR resolves from where the runner starts, not inside a path" {
  # CI passes reports/junit; the runner resolved it after cd-ing into the golden path, found nothing, and the
  # report landed outside the workspace, so trunk-upload had nothing to upload.
  stub pip 0 ok; stub pytest 0 "5 passed"
  cd "$SANDBOX"
  LANG_JUNIT_DIR=reports/junit run bash "$RUNNER" python
  [ "$status" -eq 0 ]
  [ -d "$SANDBOX/reports/junit" ]
  grep -qE "^pytest .*--junitxml=$SANDBOX/reports/junit/integration-python/python-fw\.xml" "$STUB_LOG"
}

# ── node (B262) ─────────────────────────────────────────────────────────────────────────────────────────────────────
node_path() { # node_path <name> [package.json] — a node golden path with integration tests
  mkdir -p "$SANDBOX/golden-paths/node/$1/integration"
  : > "$SANDBOX/golden-paths/node/$1/integration/items-backends.integration.js"
  printf '%s\n' "${2:-{\"scripts\": {\"test\": \"jest\"}}}" > "$SANDBOX/golden-paths/node/$1/package.json"
}

@test "node: each path installs from its lockfile and runs its *.integration.js with node --test and a JUnit report" {
  node_path fw
  stub npm 0 ok; stub node 0 "# pass 5"
  run bash "$RUNNER" node
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  grep -qE '^npm ci' "$STUB_LOG"
  ! grep -qE '^npm run (--silent )?build' "$STUB_LOG"                  # no build script: nothing to build
  grep -qE "^node --test .*--test-reporter=junit --test-reporter-destination=$SANDBOX/junit/integration-node/node-fw\.xml .*integration/items-backends\.integration\.js" "$STUB_LOG"
  [[ "$output" == *"node OK (1 path(s))"* ]]
}

@test "node: a path with a build script (TypeScript: its tests load dist/) is built before its tests run" {
  node_path nest '{"scripts": {"build": "tsc -p tsconfig.build.json", "test": "jest"}}'
  stub npm 0 ok; stub node 0 "# pass 5"
  run bash "$RUNNER" node
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(grep -nE '^npm run (--silent )?build' "$STUB_LOG" | cut -d: -f1)" -lt "$(grep -nE '^node --test' "$STUB_LOG" | cut -d: -f1)" ]
}

@test "node: a failing install or test is exit 1 and names the path" {
  node_path fw
  stub npm 1 "npm ERR! lockfile"; stub node 0 "# pass 5"
  run bash "$RUNNER" node
  [ "$status" -eq 1 ]
  [[ "$output" == *"node/fw (client install)"* ]]
  stub npm 0 ok; stub node 1 "# fail 1"
  run bash "$RUNNER" node
  [ "$status" -eq 1 ]
  [[ "$output" == *"FAILED: node/fw"* ]]
}

@test "node: no path with *.integration.js is exit 2: verifying nothing is not a pass" {
  mkdir -p "$SANDBOX/golden-paths/node/fw"
  stub npm 0 ok; stub node 0 "# pass 5"
  run bash "$RUNNER" node
  [ "$status" -eq 2 ]
  [[ "$output" == *"no integration tests found for node"* ]]
}

@test "REGRESSION (pipeline #592 class): node's bare <testcase> report is wrapped in a <testsuite>, or Trunk counts 0" {
  node_path fw
  stub npm 0 ok
  # a node stub that writes what node's junit reporter writes for top-level test() calls: cases straight under
  # <testsuites> (observed 2026-11-27, integration-node run against real backends)
  cat > "$SANDBOX/bin/node" <<'EOF'
#!/usr/bin/env bash
echo "node $*" >> "$STUB_LOG"
dest=""; for a in "$@"; do case "$a" in --test-reporter-destination=stdout) ;; --test-reporter-destination=*) dest="${a#*=}" ;; esac; done
printf '<?xml version="1.0" encoding="utf-8"?>\n<testsuites>\n\t<testcase name="t" time="0.1" classname="test"/>\n</testsuites>\n' > "$dest"
EOF
  chmod +x "$SANDBOX/bin/node"
  run bash "$RUNNER" node
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  grep -q '<testsuite name="node-fw">' "$SANDBOX/junit/integration-node/node-fw.xml"
  grep -q '</testsuite>' "$SANDBOX/junit/integration-node/node-fw.xml"
}
