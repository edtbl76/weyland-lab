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

@test "python lane installs a project's requirements-test.txt before running its pytest" {
  # B78 step 2: weyland-guard's tests import only what the CI image already has, but weyland-dagster's
  # import pyarrow/pandas — deps the fast python lane must NOT carry globally. A project declares its
  # own test deps in requirements-test.txt and the lane installs them per-project, exactly as the node
  # lane runs `npm install`. Without this the dagster suite fails at collection with ModuleNotFoundError
  # and the lane reports it as an estate defect, when the truth is the lane never gave it its deps.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/svc/tests"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/svc/tests/test_thing.py"
  printf 'pyarrow==25.0.0\n' > "$SANDBOX/scan/svc/requirements-test.txt"
  stub pip 0 "installed"
  stub pytest 0 "1 passed"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python
  [ "$status" -eq 0 ]
  grep -qE 'pip .*install.*requirements-test\.txt' "$STUB_LOG"
}

@test "python lane: a FAILED requirements-test.txt install is a broken lane (exit 2), never a pass" {
  # Fail closed. If the deps cannot be installed the lane could not do its job — that is exit 2 (lane
  # broken), the same class as a missing toolchain, NOT exit 0 (green) and NOT exit 1 (estate defect).
  # Assert the REASON, not just non-zero: project.md records a test that passed on exit 127.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/svc/tests"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/svc/tests/test_thing.py"
  printf 'pyarrow==25.0.0\n' > "$SANDBOX/scan/svc/requirements-test.txt"
  stub pip 1 "ERROR: could not install pyarrow"
  stub pytest 0 "1 passed"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python
  [ "$status" -eq 2 ]
  [[ "$output" == *"requirements-test.txt"* ]]
}

@test "python lane: a project with NO requirements-test.txt never calls pip (weyland-guard shape stays green)" {
  # Backward compatibility. weyland-guard has no requirements-test.txt; the lane must run its pytest
  # without an install step and without regressing to exit non-zero. Guards against the change calling
  # pip unconditionally (which would fail on a machine where pip is absent but the deps are preinstalled).
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/guard/tests"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/guard/tests/test_thing.py"
  stub pip 1 "pip must NOT be called"
  stub pytest 0 "1 passed"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python
  [ "$status" -eq 0 ]
  ! grep -qE '^pip ' "$STUB_LOG"
}

@test "REGRESSION: shell resolves to the dir CONTAINING the .bats files, not its parent" {
  # python and shell both have no manifest, but they need OPPOSITE roots: pytest runs from the
  # project and collects tests/, while bats must run IN the directory holding the .bats files.
  # Applying python's "parent of tests/" rule to shell resolved scripts/tests -> scripts, where
  # `bats .` finds nothing and exits 1 — a real project reported as an estate defect.
  mkdir -p "$SANDBOX/fix/shell" "$SANDBOX/scan/proj/tests"
  : > "$SANDBOX/fix/shell/hello.bats"
  : > "$SANDBOX/scan/proj/tests/thing.bats"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" shell --list-roots
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan/proj/tests"* ]]
}

@test "REGRESSION: discovery works from ANY cwd (glob expansion does not eat the pattern)" {
  # `for glob in $(test_glob_for "$lang")` is an UNQUOTED command substitution, so bash applies
  # pathname expansion to it. From the repo root `*.bats` matches nothing and survives as the
  # literal pattern find needs; from `scripts/tests` it expanded into the real filenames there and
  # discovery silently returned ZERO projects — reported as a clean "projects: 0", not an error.
  # Same code, correct or broken purely by cwd. `set -f` in discover_roots is the fix.
  mkdir -p "$SANDBOX/fix/shell" "$SANDBOX/scan/proj/tests"
  : > "$SANDBOX/fix/shell/hello.bats"
  : > "$SANDBOX/scan/proj/tests/thing.bats"
  # Run from a directory that CONTAINS .bats files — the condition that triggered the bug.
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash -c "cd '$WEYLAND_TEST_DIR' && bash '$RUNNER' shell --list-roots"
  [ "$status" -eq 0 ]
  [[ "$output" == *"projects: 1"* ]]
  [[ "$output" == *"scan/proj/tests"* ]]
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

@test "a COLLECTION error (missing dependency) is a broken lane, not an estate defect" {
  # Found running against the real repo: weyland-guard's suite could not even be COLLECTED because
  # `prometheus_client` was absent, and the runner called that exit 1 — "the estate has a failing
  # test". It does not: nothing was tested. pytest already distinguishes these (1 = tests failed,
  # 2/3/4 = collection/internal/usage error) and the lane must not flatten that distinction, or a
  # missing dependency reads as broken code.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/svc/tests"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/svc/tests/test_thing.py"
  stub_seq pytest
  stub_seq_add pytest 0 "fixture ok"
  stub_seq_add pytest 2 "ERROR collecting: ModuleNotFoundError"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python
  [ "$status" -eq 2 ]
  [[ "$output" == *"collect"* || "$output" == *"LANE BROKEN"* ]]
}

@test "pytest exit 5 (nothing collected) is a broken lane and NAMES the offending path" {
  # Found on the real tree: `scripts/test_gateway_guardrails.py` matches the test glob but is a
  # standalone diagnostic SCRIPT with no test functions, so pytest collects nothing and exits 5.
  # Skipping that silently is absence-as-success wearing a different hat — discovery matched
  # something that is not a suite, and that must be said out loud with the path, so it can be
  # renamed or excluded deliberately.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/notasuite"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/notasuite/test_looks_like_one.py"
  stub_seq pytest
  stub_seq_add pytest 0 "fixture ok"
  stub_seq_add pytest 5 "no tests ran"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python
  [ "$status" -eq 2 ]
  [[ "$output" == *"notasuite"* ]]
  [[ "$output" == *"no tests"* || "$output" == *"collected"* ]]
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
