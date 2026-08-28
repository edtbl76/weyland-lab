#!/usr/bin/env bats
#
# scripts/run-lang-tests.sh — per-language test lanes (B88).
#
# THE POINT OF THIS SUITE. B88 exists because `.woodpecker.yml`'s Python lane names ONE service by
# path (`services/weyland-guard`), so a new suite anywhere else is never executed and sits green by
# absence. The replacement must therefore be judged on one question above all others: **can a lane
# ever report success without having run anything?** Every case below is aimed at that.
#
# WHY EACH LANGUAGE SHIPS A HELLO-WORLD FIXTURE. A lane for a language with no production code yet
# (Go, Rust today) has nothing to run, and "nothing to run" is one careless line away from "green".
# The fixture removes the state entirely: every lane ALWAYS has a real project with a real test that
# must really pass. If the fixture fails, the lane itself is broken — a different fact from "the
# estate has a failing test", and the exit codes keep them apart:
#
#   exit 0  fixture passed, and every discovered real project passed
#   exit 1  a REAL project's tests failed          -> estate defect
#   exit 2  the FIXTURE failed, or the lane could not do its job -> the LANE is broken
#
# Conflating 1 and 2 means a broken runner reads exactly like broken code. Same convention as
# check-servicemonitor-coverage.sh, deliberately.
#
# ASSERT THE REASON, NOT JUST THE STATUS. `[ "$status" -ne 0 ]` passes on exit 127 (command not
# found) — recorded in project.md after a bats test written to prove a gate failed closed passed in
# the Red run against a function that did not exist. Every negative case here asserts on output text.

load helper

setup() {
  setup_stubs
  RUNNER="$REPO_ROOT/scripts/run-lang-tests.sh"
  # A throwaway repo root so discovery tests never see the real tree.
  SANDBOX="$(mktemp -d)"
  export SANDBOX
}

teardown() {
  teardown_stubs
  [ -n "${SANDBOX:-}" ] && [ -d "$SANDBOX" ] && rm -rf "$SANDBOX"
  return 0
}

# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------

@test "unknown language is refused, and the message names the valid set" {
  run bash "$RUNNER" cobol
  [ "$status" -eq 2 ]
  [[ "$output" == *"cobol"* ]]
  [[ "$output" == *"python"* ]]
  [[ "$output" == *"rust"* ]]
}

@test "no language argument is refused rather than defaulting to something" {
  run bash "$RUNNER"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* || "$output" == *"language"* ]]
}

@test "every language the lane advertises is accepted" {
  # ASSERT THE REASON, NOT `status -ne 2`. The first version of this test did exactly that and
  # PASSED in the Red run against a script that did not exist — exit 127 is not 2. That is the
  # failure mode recorded in project.md (2026-08-23), and this is the third time in this repo it
  # has turned up inside the guard written to prevent it. Requiring a known-good runner name in the
  # output cannot be satisfied by a missing command.
  for lang in python shell java go rust typescript javascript react nextjs; do
    run bash "$RUNNER" "$lang" --print-runner
    [ "$status" -eq 0 ] || {
      echo "language rejected: $lang (status $status) -- $output"
      return 1
    }
    [[ "$output" == *"pytest"* || "$output" == *"bats"* || "$output" == *"mvn"* \
       || "$output" == *"go"* || "$output" == *"cargo"* || "$output" == *"node"* ]] || {
      echo "$lang resolved to no known runner: $output"
      return 1
    }
  done
}

# ---------------------------------------------------------------------------
# The fixture is mandatory — a missing one is a BROKEN LANE, never a pass
# ---------------------------------------------------------------------------

@test "a missing fixture fails closed as a broken lane, not a green no-op" {
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/absent" bash "$RUNNER" go
  [ "$status" -eq 2 ]
  [[ "$output" == *"fixture"* ]]
  # The failure must NOT read as "nothing to test".
  [[ "$output" != *"nothing to do"* ]]
}

@test "a fixture that fails exits 2 (lane broken), never 1 (estate defect)" {
  mkdir -p "$SANDBOX/fix/go"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"
  : > "$SANDBOX/fix/go/hello_test.go"
  stub go 1 "FAIL fixture"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" bash "$RUNNER" go
  [ "$status" -eq 2 ]
  [[ "$output" == *"fixture"* ]]
}

# ---------------------------------------------------------------------------
# Success paths — and the crucial distinction between them
# ---------------------------------------------------------------------------

@test "fixture passes and no real projects exist: exit 0, but says so explicitly" {
  mkdir -p "$SANDBOX/fix/rust"
  printf '[package]\nname="fixture"\n' > "$SANDBOX/fix/rust/Cargo.toml"
  printf '#[test]\nfn t() {}\n' > "$SANDBOX/fix/rust/lib.rs"
  stub cargo 0 "test result: ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/empty" \
      bash "$RUNNER" rust
  [ "$status" -eq 0 ]
  # It must be legible that zero PRODUCTION projects ran — not silently identical to a full pass.
  [[ "$output" == *"0"* ]]
  [[ "$output" == *"fixture"* ]]
}

@test "a failing REAL project exits 1 (estate defect), not 2" {
  mkdir -p "$SANDBOX/fix/go" "$SANDBOX/scan/svc"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"
  : > "$SANDBOX/fix/go/hello_test.go"
  printf 'module svc\ngo 1.22\n' > "$SANDBOX/scan/svc/go.mod"
  # A module is only discovered when it actually CONTAINS tests — discovery keys on test files,
  # not on manifests (see the two REGRESSION cases below for why).
  : > "$SANDBOX/scan/svc/svc_test.go"
  # Fixture passes, the real one fails.
  stub_seq go
  stub_seq_add go 0 "ok"
  stub_seq_add go 1 "FAIL svc"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" go
  [ "$status" -eq 1 ]
  [[ "$output" == *"svc"* ]]
}

# ---------------------------------------------------------------------------
# Fail closed when the toolchain is absent — never skip
# ---------------------------------------------------------------------------

@test "sources present but the toolchain is missing fails closed and names the tool" {
  mkdir -p "$SANDBOX/fix/rust"
  printf '[package]\nname="fixture"\n' > "$SANDBOX/fix/rust/Cargo.toml"
  printf '#[test]\nfn t() {}\n' > "$SANDBOX/fix/rust/lib.rs"
  # No `cargo` stub is created, and PATH is the stub dir first — so cargo is genuinely absent.
  run env PATH="$STUB_DIR:/usr/bin:/bin" WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" \
      bash "$RUNNER" rust
  [ "$status" -eq 2 ]
  [[ "$output" == *"cargo"* ]]
  # "Toolchain missing" must never be reported as a pass or a skip.
  [[ "$output" != *"PASS"* ]]
}

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@test "the fixture tree is excluded from real-project discovery (not double-counted)" {
  mkdir -p "$SANDBOX/fix/go"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"
  : > "$SANDBOX/fix/go/hello_test.go"
  stub go 0 "ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/fix" \
      bash "$RUNNER" go --list-roots
  [ "$status" -eq 0 ]
  # The fixture must appear exactly once, as the fixture — not again as a discovered project.
  [ "$(echo "$output" | grep -c 'fix/go')" -eq 1 ]
}

@test "multiple real project roots are all discovered, not just the first" {
  mkdir -p "$SANDBOX/fix/go" "$SANDBOX/scan/a" "$SANDBOX/scan/b"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"
  : > "$SANDBOX/fix/go/hello_test.go"
  printf 'module a\ngo 1.22\n' > "$SANDBOX/scan/a/go.mod"; : > "$SANDBOX/scan/a/a_test.go"
  printf 'module b\ngo 1.22\n' > "$SANDBOX/scan/b/go.mod"; : > "$SANDBOX/scan/b/b_test.go"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" go --list-roots
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan/a"* ]]
  [[ "$output" == *"scan/b"* ]]
}

@test "REGRESSION: a python dir with tests/ but NO manifest is discovered (the weyland-guard shape)" {
  # Found by running against the real tree, not by a stub: weyland-guard is the ONLY python project
  # in this repo with a test suite, and it has no requirements.txt and no pyproject.toml. Keying
  # discovery on a manifest missed the one suite CI actually runs today — a straight regression.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/guard/tests"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/guard/tests/test_thing.py"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python --list-roots
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan/guard"* ]]
}

@test "REGRESSION: a python dir with a manifest but NO tests is NOT discovered" {
  # The mirror of the above. pytest exits 5 ("no tests collected") in such a directory, so
  # discovering it turns five test-less services into five reported FAILURES.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/svc"
  : > "$SANDBOX/fix/python/test_hello.py"
  printf 'flask\n' > "$SANDBOX/scan/svc/requirements.txt"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python --list-roots
  [ "$status" -eq 0 ]
  [[ "$output" != *"scan/svc"* ]]
}

@test "a go test file resolves UP to its module root, not its own directory" {
  # `go test` must run at the module root; discovering the test file's directory would run it in a
  # package dir with no go.mod and fail for the wrong reason.
  mkdir -p "$SANDBOX/fix/go" "$SANDBOX/scan/mod/internal/deep"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"
  printf 'module m\ngo 1.22\n'       > "$SANDBOX/scan/mod/go.mod"
  : > "$SANDBOX/scan/mod/internal/deep/thing_test.go"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" go --list-roots
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan/mod"* ]]
  [[ "$output" != *"internal/deep"* ]]
}

@test "vendor and build directories are not mistaken for project roots" {
  mkdir -p "$SANDBOX/fix/javascript" "$SANDBOX/scan/app/node_modules/pkg"
  printf '{"name":"fixture"}' > "$SANDBOX/fix/javascript/package.json"
  : > "$SANDBOX/fix/javascript/hello.test.js"
  printf '{"name":"app"}'     > "$SANDBOX/scan/app/package.json"
  : > "$SANDBOX/scan/app/app.test.js"
  printf '{"name":"vendored"}' > "$SANDBOX/scan/app/node_modules/pkg/package.json"
  : > "$SANDBOX/scan/app/node_modules/pkg/dep.test.js"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" javascript --list-roots
  [ "$status" -eq 0 ]
  [[ "$output" != *"node_modules"* ]]
}

# ---------------------------------------------------------------------------
# One node runner, four archetypes
# ---------------------------------------------------------------------------

@test "typescript / javascript / react / nextjs all resolve to the node runner" {
  for lang in typescript javascript react nextjs; do
    run bash "$RUNNER" "$lang" --print-runner
    [ "$status" -eq 0 ]
    [[ "$output" == *"node"* ]] || {
      echo "$lang did not resolve to the node runner: $output"
      return 1
    }
  done
}

@test "each language resolves to its own expected runner" {
  run bash "$RUNNER" python --print-runner
  [[ "$output" == *"pytest"* ]]
  run bash "$RUNNER" shell --print-runner
  [[ "$output" == *"bats"* ]]
  run bash "$RUNNER" java --print-runner
  [[ "$output" == *"mvn"* || "$output" == *"maven"* ]]
  run bash "$RUNNER" go --print-runner
  [[ "$output" == *"go"* ]]
  run bash "$RUNNER" rust --print-runner
  [[ "$output" == *"cargo"* ]]
}

# ---------------------------------------------------------------------------
# The negative case — prove a lane can actually FAIL
# ---------------------------------------------------------------------------

@test "--self-check proves the runner propagates a deliberate failure" {
  mkdir -p "$SANDBOX/fix/go"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"
  : > "$SANDBOX/fix/go/hello_test.go"
  # In self-check the fixture's KNOWN-FAILING test runs; a runner that swallowed it would exit 0
  # and this assertion is the whole point of the mode.
  stub go 1 "FAIL: deliberate"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" bash "$RUNNER" go --self-check
  [ "$status" -eq 0 ]
  [[ "$output" == *"propagat"* || "$output" == *"self-check"* ]]
}

@test "--self-check FAILS when the runner swallows a failing test" {
  mkdir -p "$SANDBOX/fix/go"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"
  : > "$SANDBOX/fix/go/hello_test.go"
  # The deliberately-failing test "passes" -> the runner is not propagating failure -> self-check
  # must report the lane broken.
  stub go 0 "ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" bash "$RUNNER" go --self-check
  [ "$status" -eq 2 ]
}
