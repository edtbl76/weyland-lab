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

@test "a selfcheck/ subdir is never discovered as its own project (golden-path shape, B153)" {
  # A golden path (golden-paths/<lang>/<fw>) carries a selfcheck/ companion. For python (no manifest)
  # the selfcheck test file used to resolve to its OWN dir → a second, always-failing 'project'.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/gp/selfcheck"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/gp/test_gp.py"
  : > "$SANDBOX/scan/gp/selfcheck/test_deliberate.py"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python --list-roots
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan/gp"* ]]                                  # the golden path IS a project
  [ "$(echo "$output" | grep -c 'selfcheck')" -eq 0 ]            # its selfcheck is NOT a separate one
}

@test "the coding-agent eval fixture tree is never discovered as a project (B104)" {
  # eval/coding-agents/tasks/<id>/ ships a deliberately-buggy Red test + a solution/. Discovering it
  # runs a test built to FAIL and reds the lane (test-python did, 2026-09-10). It must be excluded.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/eval/coding-agents/tasks/py-bug/workdir"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/eval/coding-agents/tasks/py-bug/workdir/test_stats.py"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python --list-roots
  [ "$status" -eq 0 ]
  [ "$(echo "$output" | grep -c 'eval/coding-agents')" -eq 0 ]   # the eval fixture is NOT a project
}

@test "the SDD bake-off's hidden judges are never discovered as a project (B86)" {
  # eval/sdd-bakeoff/reference/judge*-<task>/ hold test_*.py files that judge a TRIAL's service (SERVICE_DIR); run
  # standalone they have nothing to test and fail. Same class as the coding-agent fixtures above.
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/eval/sdd-bakeoff/reference/judge-green"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/eval/sdd-bakeoff/reference/judge-green/test_contract.py"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python --list-roots
  [ "$status" -eq 0 ]
  [ "$(echo "$output" | grep -c 'eval/sdd-bakeoff')" -eq 0 ]   # the judges are NOT a project
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

# ---------------------------------------------------------------------------
# JUnit reports for Trunk Flaky Tests (B189). LANG_JUNIT_DIR=<dir> makes every NORMAL run (fixture and
# real projects) leave a report at <dir>/<lang>/<project>.xml (or a <project>/ dir of the runner's own
# files). Self-check NEVER writes one: its deliberate failure would reach Trunk as a test that fails on
# every build, which teaches everyone to ignore red. Unset = the lane behaves exactly as before.
# ---------------------------------------------------------------------------

py_tree() {
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/svc/tests"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/svc/tests/test_thing.py"
}

@test "junit: python passes --junitxml for the fixture AND each real project" {
  py_tree
  stub pytest 0 "1 passed"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" python
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  called_with pytest "--junitxml=$SANDBOX/junit/python/fixture.xml"
  called_with pytest "--junitxml=$SANDBOX/junit/python/svc.xml"
}

@test "junit: unset LANG_JUNIT_DIR passes no report flag (the lane is unchanged)" {
  py_tree
  stub pytest 0 "1 passed"
  run env -u LANG_JUNIT_DIR WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      bash "$RUNNER" python
  [ "$status" -eq 0 ]
  not_called_with pytest "--junitxml"
}

@test "junit: --self-check never writes a report, even with LANG_JUNIT_DIR set" {
  mkdir -p "$SANDBOX/fix/python/selfcheck"
  : > "$SANDBOX/fix/python/test_hello.py"
  stub pytest 1 "1 failed"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" LANG_JUNIT_DIR="$SANDBOX/junit" \
      bash "$RUNNER" python --self-check
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  not_called_with pytest "--junitxml"
  [ ! -e "$SANDBOX/junit" ]
}

@test "junit: a nested project's report name keeps its path, so two projects never collide" {
  mkdir -p "$SANDBOX/fix/python" "$SANDBOX/scan/services/a/tests" "$SANDBOX/scan/services/b/tests"
  : > "$SANDBOX/fix/python/test_hello.py"
  : > "$SANDBOX/scan/services/a/tests/test_a.py"
  : > "$SANDBOX/scan/services/b/tests/test_b.py"
  stub pytest 0 "1 passed"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" python
  [ "$status" -eq 0 ]
  called_with pytest "--junitxml=$SANDBOX/junit/python/services__a.xml"
  called_with pytest "--junitxml=$SANDBOX/junit/python/services__b.xml"
}

@test "junit: java harvests Surefire's own reports, EVEN when the tests failed" {
  # Maven writes target/surefire-reports/TEST-*.xml itself; the lane copies them out after the run.
  # The failed run is the one Trunk most needs to see, so the copy must not depend on mvn's exit.
  mkdir -p "$SANDBOX/fix/java" "$SANDBOX/scan/svc/src/test"
  printf '<project/>\n' > "$SANDBOX/fix/java/pom.xml"
  : > "$SANDBOX/fix/java/HelloTest.java"
  printf '<project/>\n' > "$SANDBOX/scan/svc/pom.xml"
  : > "$SANDBOX/scan/svc/src/test/ThingTest.java"
  cat > "$STUB_DIR/mvn" <<'EOF'
#!/usr/bin/env bash
mkdir -p target/surefire-reports
printf '<testsuite name="T" tests="1"/>\n' > target/surefire-reports/TEST-T.xml
[ "$(basename "$PWD")" = svc ] && exit 1 || exit 0
EOF
  chmod +x "$STUB_DIR/mvn"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" java
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [ -f "$SANDBOX/junit/java/fixture/TEST-T.xml" ]
  [ -f "$SANDBOX/junit/java/svc/TEST-T.xml" ]
}

@test "junit: harvest copies only reports the NORMAL run wrote, never the self-check's leftover" {
  # Found 2026-11-06 in pipeline #589: CI runs --self-check first in the same checkout, Surefire/sbt leave the
  # deliberate failure's report in target/, and the normal run's harvest copied it too — so Trunk saw the
  # self-check test failing on every green build (java 1/36, scala 1/5). Self-check must never reach Trunk.
  mkdir -p "$SANDBOX/fix/java/target/surefire-reports" "$SANDBOX/scan"
  printf '<project/>\n' > "$SANDBOX/fix/java/pom.xml"
  : > "$SANDBOX/fix/java/HelloTest.java"
  printf '<testsuite name="D" tests="1"><testcase classname="D" name="deliberate"><failure/></testcase></testsuite>\n' \
    > "$SANDBOX/fix/java/target/surefire-reports/TEST-Deliberate.xml"
  touch -t 202001010000 "$SANDBOX/fix/java/target/surefire-reports/TEST-Deliberate.xml"   # BusyBox touch: no relative dates
  cat > "$STUB_DIR/mvn" <<'EOF'
#!/usr/bin/env bash
mkdir -p target/surefire-reports
printf '<testsuite name="T" tests="1"><testcase classname="T" name="t"/></testsuite>\n' > target/surefire-reports/TEST-T.xml
EOF
  chmod +x "$STUB_DIR/mvn"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" java
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ -f "$SANDBOX/junit/java/fixture/TEST-T.xml" ]
  [ ! -e "$SANDBOX/junit/java/fixture/TEST-Deliberate.xml" ]
}

@test "junit: harvested reports with test cases do NOT trigger the no-report warning" {
  # Found 2026-11-06 on the real swift lane: the check was `cat "$JB.xml" <harvested files> | grep -q`, and
  # under pipefail cat's failure on the absent $JB.xml failed the pipeline although grep matched — every
  # harvested lane warned NO JUNIT REPORT about reports that were there. The pipeline-status trap.
  mkdir -p "$SANDBOX/fix/java" "$SANDBOX/scan"
  printf '<project/>\n' > "$SANDBOX/fix/java/pom.xml"
  : > "$SANDBOX/fix/java/HelloTest.java"
  cat > "$STUB_DIR/mvn" <<'EOF'
#!/usr/bin/env bash
mkdir -p target/surefire-reports
printf '<testsuite name="T" tests="1"><testcase classname="T" name="t"/></testsuite>\n' > target/surefire-reports/TEST-T.xml
EOF
  chmod +x "$STUB_DIR/mvn"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" java
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" != *"NO JUNIT REPORT"* ]]
}

@test "junit: a runner that should have written a report and did not is named, not silently skipped" {
  # Absence is never success: a lane that ran tests but left no report would make Trunk show the
  # source as quiet. The lane still passes (the TESTS passed), but it says so out loud.
  mkdir -p "$SANDBOX/fix/java" "$SANDBOX/scan"
  printf '<project/>\n' > "$SANDBOX/fix/java/pom.xml"
  : > "$SANDBOX/fix/java/HelloTest.java"
  stub mvn 0 "BUILD SUCCESS"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" java
  [ "$status" -eq 0 ]
  [[ "$output" == *"NO JUNIT REPORT"*"java"* ]]
}

@test "junit: a report with ZERO test cases counts as no report" {
  # Found 2026-11-06 on the real swift lane: without --parallel, `swift test --xunit-output` writes only
  # the swift-testing file, with 0 cases, while the XCTest suite ran. An empty file is absence wearing a
  # file's name, so the lane must still say NO JUNIT REPORT.
  mkdir -p "$SANDBOX/fix/java" "$SANDBOX/scan"
  printf '<project/>\n' > "$SANDBOX/fix/java/pom.xml"
  : > "$SANDBOX/fix/java/HelloTest.java"
  cat > "$STUB_DIR/mvn" <<'EOF'
#!/usr/bin/env bash
mkdir -p target/surefire-reports
printf '<testsuites><testsuite name="T" tests="0"></testsuite></testsuites>\n' > target/surefire-reports/TEST-T.xml
EOF
  chmod +x "$STUB_DIR/mvn"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" java
  [ "$status" -eq 0 ]
  [[ "$output" == *"NO JUNIT REPORT"*"java"* ]]
}

@test "junit: swift runs --parallel when reporting (XCTest's report only exists with it)" {
  mkdir -p "$SANDBOX/fix/swift/Tests" "$SANDBOX/scan"
  : > "$SANDBOX/fix/swift/Package.swift"
  : > "$SANDBOX/fix/swift/Tests/HelloTests.swift"
  stub swift 0 "ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" swift
  called_with swift "--parallel"
  called_with swift "--xunit-output $SANDBOX/junit/swift/fixture/swift.xml"
}

# Phase 2a (B189): runners whose JUnit is built in — lua (busted), r (testthat), cpp (doctest), erlang (eunit
# surefire), and node's vitest / `node --test`. Jest needs a package (phase 2b) and must say so, not look quiet.

@test "junit: lua runs busted with its junit output into the report file" {
  mkdir -p "$SANDBOX/fix/lua/spec" "$SANDBOX/scan"
  : > "$SANDBOX/fix/lua/.busted"; : > "$SANDBOX/fix/lua/spec/hello_spec.lua"
  stub busted 0 "ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" lua
  called_with busted "-o junit -Xoutput $SANDBOX/junit/lua/fixture.xml"
}

@test "junit: r does not report yet (JunitReporter needs xml2) and says so; the lane is unchanged" {
  # Found 2026-11-06 in rocker/r-ver:4: testthat's JunitReporter needs the xml2 package, absent from the CI
  # image, and wiring it in broke the lane. R moves to phase 2b (a package install, proposed first).
  mkdir -p "$SANDBOX/fix/r/tests" "$SANDBOX/scan"
  : > "$SANDBOX/fix/r/plumber.R"; : > "$SANDBOX/fix/r/tests/test-hello.R"
  stub Rscript 0 "ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" r
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  not_called_with Rscript "JunitReporter"
  [[ "$output" == *"r has no JUnit reporter yet"* ]]
}

@test "junit: cpp runs the doctest binary with the junit reporter" {
  mkdir -p "$SANDBOX/fix/cpp/build" "$SANDBOX/scan"
  : > "$SANDBOX/fix/cpp/CMakeLists.txt"; : > "$SANDBOX/fix/cpp/hello_test.cpp"
  stub cmake 0 ""
  printf '#!/usr/bin/env bash\nprintf "unit_tests %%s\\n" "$*" >> "%s"\n' "$STUB_LOG" > "$SANDBOX/fix/cpp/build/unit_tests"
  chmod +x "$SANDBOX/fix/cpp/build/unit_tests"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" cpp
  called_with unit_tests "--reporters=junit --out=$SANDBOX/junit/cpp/fixture.xml"
}

@test "junit: erlang runs eunit with a generated config that adds the surefire report, golden path untouched" {
  mkdir -p "$SANDBOX/fix/erlang/test" "$SANDBOX/scan"
  printf '{deps, []}.\n' > "$SANDBOX/fix/erlang/rebar.config"
  : > "$SANDBOX/fix/erlang/test/hello_tests.erl"
  cat > "$STUB_DIR/rebar3" <<EOF
#!/usr/bin/env bash
printf 'rebar3 %s REBAR_CONFIG=%s\n' "\$*" "\${REBAR_CONFIG:-}" >> "$STUB_LOG"
[ -n "\${REBAR_CONFIG:-}" ] && cat "\$REBAR_CONFIG" >> "$STUB_LOG"
exit 0
EOF
  chmod +x "$STUB_DIR/rebar3"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" erlang
  grep -qF "{deps, []}." "$STUB_LOG"
  grep -qF "eunit_surefire" "$STUB_LOG"
  grep -qF "$SANDBOX/junit/erlang/fixture" "$STUB_LOG"
  [ "$(cat "$SANDBOX/fix/erlang/rebar.config")" = "{deps, []}." ]
}

node_project() {   # node_project <dir> <test script or empty for node --test>
  mkdir -p "$1/node_modules"
  if [ -n "$2" ]; then printf '{"scripts":{"test":"%s"}}\n' "$2" > "$1/package.json"
  else printf '{}\n' > "$1/package.json"; fi
  : > "$1/app.test.js"
}

@test "junit: node lanes report into ONE shared variant, so a project run by four lanes is counted once" {
  node_project "$SANDBOX/fix/typescript" "vitest run"
  node_project "$SANDBOX/fix/javascript" "vitest run"
  node_project "$SANDBOX/scan/shared" "vitest run"
  stub npm 0 "ok"
  stub node 0 ""   # the lane's "has a test script?" probe (`node -e …`) answers yes
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" typescript
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" javascript
  [ "$(calls_to npm | grep -c -- "--outputFile.junit=$SANDBOX/junit/node/shared.xml")" -eq 2 ]
  not_called_with npm "junit/typescript/"
  not_called_with npm "junit/javascript/"
}

@test "junit: node --test projects use the built-in junit reporter and keep the console one" {
  node_project "$SANDBOX/fix/typescript" ""
  mkdir -p "$SANDBOX/scan"
  stub_dispatch node
  stub_case node '-e' 1 ''   # the "has a test script?" probe answers no -> the node --test branch
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" typescript
  called_with node "--test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit"
  called_with node "--test-reporter-destination=$SANDBOX/junit/node/"
}

@test "junit: go runs go test through gotestsum with --junitfile and the SAME go test flags" {
  mkdir -p "$SANDBOX/fix/go" "$SANDBOX/scan"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"; : > "$SANDBOX/fix/go/hello_test.go"
  stub gotestsum 0 "ok"
  stub go 0 "ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" go
  called_with gotestsum "--junitfile $SANDBOX/junit/go/fixture.xml"
  called_with gotestsum "-- -race -coverprofile=coverage.out ./..."
  not_called_with go "test"
}

@test "junit: go without gotestsum on PATH runs as before and says why there is no report" {
  mkdir -p "$SANDBOX/fix/go" "$SANDBOX/scan"
  printf 'module fixture\ngo 1.22\n' > "$SANDBOX/fix/go/go.mod"; : > "$SANDBOX/fix/go/hello_test.go"
  stub go 0 "ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" go
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  called_with go "test -race -coverprofile=coverage.out ./..."
  [[ "$output" == *"gotestsum"*"not on PATH"* ]]
  [[ "$output" != *"NO JUNIT REPORT"* ]]
}

@test "junit: rust runs cargo nextest with a generated config naming the report path; the project gets no config file" {
  # Observed 2026-11-06 in rust:1-slim with nextest 0.9.149: an outside --config-file with
  # [profile.default.junit] path = "<absolute>" writes the report there.
  mkdir -p "$SANDBOX/fix/rust/src" "$SANDBOX/scan"
  printf '[package]\nname="f"\n' > "$SANDBOX/fix/rust/Cargo.toml"; : > "$SANDBOX/fix/rust/src/lib.rs"
  cat > "$STUB_DIR/cargo" <<EOF
#!/usr/bin/env bash
printf 'cargo %s\n' "\$*" >> "$STUB_LOG"
for a in "\$@"; do [ -f "\$a" ] && cat "\$a" >> "$STUB_LOG"; done
exit 0
EOF
  chmod +x "$STUB_DIR/cargo"
  stub cargo-nextest 0 ""
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" rust
  called_with cargo "nextest run --config-file $SANDBOX/junit/rust/fixture.nextest.toml"
  grep -qF "path = \"$SANDBOX/junit/rust/fixture.xml\"" "$STUB_LOG"
  [ ! -e "$SANDBOX/junit/rust/fixture.nextest.toml" ]
  [ ! -e "$SANDBOX/fix/rust/.config" ]
}

@test "junit: rust without cargo-nextest runs cargo test as before and says why" {
  mkdir -p "$SANDBOX/fix/rust/src" "$SANDBOX/scan"
  printf '[package]\nname="f"\n' > "$SANDBOX/fix/rust/Cargo.toml"; : > "$SANDBOX/fix/rust/src/lib.rs"
  stub cargo 0 "test result: ok"
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" rust
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  called_with cargo "test"
  not_called_with cargo "nextest"
  [[ "$output" == *"cargo-nextest is not on PATH"* ]]
}

@test "junit: with JEST_JUNIT_REPORTER set, a jest project runs jest-junit beside the default reporter" {
  node_project "$SANDBOX/fix/typescript" "jest --testPathIgnorePatterns /node_modules/"
  mkdir -p "$SANDBOX/scan"
  cat > "$STUB_DIR/npm" <<EOF
#!/usr/bin/env bash
printf 'npm %s JEST_JUNIT_OUTPUT_FILE=%s\n' "\$*" "\${JEST_JUNIT_OUTPUT_FILE:-}" >> "$STUB_LOG"
EOF
  chmod +x "$STUB_DIR/npm"
  stub node 0 ""
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" JEST_JUNIT_REPORTER=/tmp/jest-junit/node_modules/jest-junit bash "$RUNNER" typescript
  called_with npm "--reporters=default --reporters=/tmp/jest-junit/node_modules/jest-junit"
  called_with npm "JEST_JUNIT_OUTPUT_FILE=$SANDBOX/junit/node/"
  [[ "$output" != *"phase 2b"* ]]
}

@test "junit: a jest project is not reported yet and says why (phase 2b), never a silent gap" {
  node_project "$SANDBOX/fix/typescript" "jest"
  mkdir -p "$SANDBOX/scan"
  stub npm 0 "ok"
  stub node 0 ""
  run env WEYLAND_LANG_FIXTURE_DIR="$SANDBOX/fix" WEYLAND_LANG_SCAN_ROOT="$SANDBOX/scan" \
      LANG_JUNIT_DIR="$SANDBOX/junit" bash "$RUNNER" typescript
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  not_called_with npm "--reporter"
  [[ "$output" == *"jest"*"phase 2b"* ]]
  [[ "$output" != *"NO JUNIT REPORT"* ]]
}
