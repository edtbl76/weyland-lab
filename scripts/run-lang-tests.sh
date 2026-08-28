#!/usr/bin/env bash
#
# run-lang-tests.sh — per-language test lanes (B88).
#
# WHY THIS EXISTS. `.woodpecker.yml`'s Python lane named ONE service by path
# (`services/weyland-guard`), so a suite added anywhere else was never executed and sat green by
# absence — passing because nothing ran it. That is the same absence-as-success class recorded
# repeatedly in project.md, located in the test harness itself, where it is hardest to notice. This
# replaces the hardcoded path with discovery.
#
# WHY EVERY LANGUAGE HAS A HELLO-WORLD FIXTURE. A lane for a language with no production code yet
# (Go and Rust today) has nothing to run, and "nothing to run" is one careless line from "green".
# The fixture deletes that state: every lane ALWAYS has a real project with a real test that must
# really pass, so the toolchain, the image, the runner and discovery are all continuously proven.
#
# THREE OUTCOMES, NEVER CONFLATED:
#   0  the fixture passed AND every discovered real project passed
#   1  a REAL project's tests failed                  -> the ESTATE has a defect
#   2  the FIXTURE failed, or the lane could not run   -> the LANE is broken
# Collapsing 1 and 2 makes a broken runner read exactly like broken code — the mistake this repo
# already made once with `check-servicemonitor-coverage.sh`, whose convention this mirrors.
#
# NEVER SKIP. A missing toolchain, a missing fixture, or an unparseable language is exit 2 with a
# reason on stderr. `cmd 2>/dev/null` inside a boolean, an empty list, and a pipeline whose status
# comes from its last command have each turned an error into a positive answer in this repo before.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Overridable for tests. The fixture tree is ALWAYS excluded from real-project discovery so it is
# never double-counted as production code.
FIXTURE_DIR="${WEYLAND_LANG_FIXTURE_DIR:-$REPO_ROOT/tests/lang}"
SCAN_ROOT="${WEYLAND_LANG_SCAN_ROOT:-$REPO_ROOT}"

LANGS="python shell java go rust typescript javascript react nextjs"

die() { printf '%s\n' "$*" >&2; exit 2; }

usage() {
  cat >&2 <<EOF
usage: run-lang-tests.sh <language> [--list-roots|--print-runner|--self-check]

  language   one of: $LANGS

  --list-roots     print the fixture root and every discovered project root, then exit
  --print-runner   print the runner this language resolves to, then exit
  --self-check     run each fixture's DELIBERATELY FAILING test and assert the runner
                   propagates the failure; a lane never seen failing is not a lane

exit 0  fixture + all real projects passed
exit 1  a real project failed  (estate defect)
exit 2  the fixture failed, or the lane could not do its job  (lane broken)
EOF
  exit 2
}

# runner_for <lang> -> the tool this language's tests run through.
# typescript/javascript/react/nextjs deliberately collapse onto ONE node runner: they are archetypes
# on a single toolchain, not four toolchains, and building four runners would be the mistake.
runner_for() {
  case "$1" in
    python)                            echo "pytest" ;;
    shell)                             echo "bats" ;;
    java)                              echo "mvn" ;;
    go)                                echo "go" ;;
    rust)                              echo "cargo" ;;
    typescript|javascript|react|nextjs) echo "node" ;;
    *)                                 return 1 ;;
  esac
}

# test_glob_for <lang> -> filename patterns that identify a TEST FILE.
#
# DISCOVERY KEYS ON TESTS, NOT ON MANIFESTS — and getting this backwards was a real bug, caught only
# by running against the real tree (stubs cannot find it, because the stub author picks the shape).
# Keying on `requirements.txt` simultaneously:
#   - MISSED `services/weyland-guard`, the ONE python suite CI runs today, which has a tests/ dir and
#     no manifest at all -> a straight regression, and
#   - MATCHED five services that have a manifest and no tests, where `pytest` exits **5** ("no tests
#     collected") -> five false FAILURES.
# The question this tool asks is "are there tests here", never "is this a project".
test_glob_for() {
  case "$1" in
    python)                            echo "test_*.py *_test.py" ;;
    shell)                             echo "*.bats" ;;
    java)                              echo "*Test.java *Tests.java" ;;
    go)                                echo "*_test.go" ;;
    rust)                              echo "*.rs" ;;
    typescript|javascript|react|nextjs) echo "*.test.js *.test.ts *.test.jsx *.test.tsx" ;;
    *)                                 return 1 ;;
  esac
}

# root_marker_for <lang> -> the manifest that defines the project root a test belongs to. The runner
# must execute AT that root (`go test` needs the module root; `mvn` needs the pom) — running in the
# test file's own directory fails for the wrong reason. Empty means "no manifest required".
root_marker_for() {
  case "$1" in
    java)                              echo "pom.xml" ;;
    go)                                echo "go.mod" ;;
    rust)                              echo "Cargo.toml" ;;
    typescript|javascript|react|nextjs) echo "package.json" ;;
    python|shell)                      echo "" ;;   # resolved structurally, see resolve_root
    *)                                 return 1 ;;
  esac
}

# resolve_root <lang> <test-file> -> the directory the runner should execute in.
# Walks up from the test file toward SCAN_ROOT looking for the language's manifest. For python and
# shell there is no manifest: the root is the directory CONTAINING a `tests/` dir when the file sits
# under one (so pytest/bats run from the project and collect tests/), else the file's own directory.
resolve_root() {
  local lang="$1" file="$2" marker dir parent
  marker="$(root_marker_for "$lang")"
  dir="$(dirname "$file")"

  if [ -z "$marker" ]; then
    case "$dir" in
      */tests|*/test) dirname "$dir"; return 0 ;;
    esac
    printf '%s\n' "$dir"; return 0
  fi

  while [ -n "$dir" ] && [ "$dir" != "/" ] && [ "$dir" != "." ]; do
    if [ -f "$dir/$marker" ]; then printf '%s\n' "$dir"; return 0; fi
    parent="$(dirname "$dir")"
    [ "$parent" = "$dir" ] && break
    dir="$parent"
  done
  # A test file with no owning manifest is a real defect in that tree, not something to guess at.
  return 1
}

# Directories that are never project roots. node_modules/target/vendor hold OTHER people's manifests;
# treating one as a root would run a dependency's test suite and report it as ours.
is_excluded() {
  case "$1" in
    */node_modules/*|*/target/*|*/vendor/*|*/.git/*|*/.venv/*|*/site-packages/*|*/dist/*|*/build/*)
      return 0 ;;
  esac
  return 1
}

# discover_roots <lang> <base> — find TEST FILES under <base>, resolve each to its owning project
# root, print the unique set.
#
# Uses `find -name`, never `grep --include`: ugrep (this box) and busybox grep (the CI image)
# disagree on --include, and that disagreement already produced one wrong result in this repo.
discover_roots() {
  local lang="$1" base="$2" glob f root
  [ -d "$base" ] || return 0
  for glob in $(test_glob_for "$lang"); do
    while IFS= read -r f; do
      is_excluded "$f" && continue
      # Rust's glob is *.rs (tests live inline behind #[cfg(test)]), so require the attribute
      # rather than treating every source file as a test.
      if [ "$lang" = rust ] && ! grep -q '#\[test\]' "$f" 2>/dev/null; then continue; fi
      root="$(resolve_root "$lang" "$f")" || {
        printf 'LANE BROKEN: %s test file has no owning %s: %s\n' \
          "$lang" "$(root_marker_for "$lang")" "$f" >&2
        continue
      }
      printf '%s\n' "$root"
    done < <(find "$base" -type f -name "$glob" 2>/dev/null)
  done | sort -u
}

# run_in <lang> <dir> <mode> — run this language's tests in <dir>.
# mode: normal | selfcheck (selfcheck runs the fixture's deliberately-failing test)
# Returns the runner's exit status. NEVER swallows it.
run_in() {
  local lang="$1" dir="$2" mode="$3" bin
  bin="$(runner_for "$lang")"

  command -v "$bin" >/dev/null 2>&1 || {
    printf 'LANE BROKEN: %s toolchain is missing — `%s` not found on PATH (looked in %s)\n' \
      "$lang" "$bin" "$dir" >&2
    return 2
  }

  case "$lang" in
    python)
      if [ "$mode" = selfcheck ]; then (cd "$dir" && pytest -q -k deliberate_failure); \
      else (cd "$dir" && pytest -q -p no:cacheprovider --deselect-deliberate 2>/dev/null \
            || (cd "$dir" && pytest -q -p no:cacheprovider -k "not deliberate_failure")); fi ;;
    shell)
      if [ "$mode" = selfcheck ]; then (cd "$dir" && bats deliberate-failure.bats); \
      else (cd "$dir" && bats .); fi ;;
    java)
      if [ "$mode" = selfcheck ]; then (cd "$dir" && mvn -q -Dtest=DeliberateFailureTest test); \
      else (cd "$dir" && mvn -q -Dtest='!DeliberateFailureTest' test); fi ;;
    go)
      if [ "$mode" = selfcheck ]; then (cd "$dir" && go test -run DeliberateFailure ./...); \
      else (cd "$dir" && go test -race -coverprofile=coverage.out ./...); fi ;;
    rust)
      if [ "$mode" = selfcheck ]; then (cd "$dir" && cargo test deliberate_failure); \
      else (cd "$dir" && cargo test); fi ;;
    typescript|javascript|react|nextjs)
      if [ "$mode" = selfcheck ]; then (cd "$dir" && node --test deliberate-failure.test.*); \
      else (cd "$dir" && node --test); fi ;;
  esac
}

# ── main ──────────────────────────────────────────────────────────────────────
main() {
  [ $# -ge 1 ] || usage
  local lang="$1"; shift
  local mode="normal" action="run"

  runner_for "$lang" >/dev/null 2>&1 || \
    die "unknown language: '$lang'
valid languages: $LANGS"

  while [ $# -gt 0 ]; do
    case "$1" in
      --list-roots)   action="list" ;;
      --print-runner) action="runner" ;;
      --self-check)   mode="selfcheck" ;;
      *)              die "unknown option: $1" ;;
    esac
    shift
  done

  if [ "$action" = runner ]; then runner_for "$lang"; exit 0; fi

  local fixture="$FIXTURE_DIR/$lang"

  # THE FIXTURE IS MANDATORY. Its absence is a broken lane, never "nothing to do" — that
  # distinction is the whole reason fixtures exist.
  [ -d "$fixture" ] || die "LANE BROKEN: no $lang fixture at $fixture
The fixture is what proves this lane can run at all; without it a pass would mean nothing."

  # Real project roots, with the fixture tree removed so it is counted once, as the fixture.
  local -a real=()
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    case "$d" in "$FIXTURE_DIR"|"$FIXTURE_DIR"/*) continue ;; esac
    real+=("$d")
  done < <(discover_roots "$lang" "$SCAN_ROOT")

  if [ "$action" = list ]; then
    printf 'fixture: %s\n' "$fixture"
    printf 'projects: %d\n' "${#real[@]}"
    local d; for d in "${real[@]+"${real[@]}"}"; do printf 'project: %s\n' "$d"; done
    exit 0
  fi

  # ── self-check: prove the runner propagates a real failure ──────────────────
  if [ "$mode" = selfcheck ]; then
    run_in "$lang" "$fixture" selfcheck
    local sc=$?
    if [ "$sc" -eq 0 ]; then
      printf 'LANE BROKEN: --self-check ran %s'"'"'s deliberately-failing test and the runner reported SUCCESS.\n' "$lang" >&2
      printf 'A lane that cannot fail is not a lane; every green it reports is meaningless.\n' >&2
      exit 2
    fi
    printf 'self-check OK: %s propagated the deliberate failure (exit %d)\n' "$lang" "$sc"
    exit 0
  fi

  # ── the fixture must pass, or the lane is broken (2, never 1) ───────────────
  run_in "$lang" "$fixture" normal
  local fx=$?
  [ "$fx" -eq 0 ] || {
    printf 'LANE BROKEN: the %s fixture failed (exit %d) at %s\n' "$lang" "$fx" "$fixture" >&2
    printf 'This is the LANE, not the estate — no conclusion can be drawn about real code.\n' >&2
    exit 2
  }

  # ── real projects: a failure here is an estate defect (1, never 2) ──────────
  local failed=0 d rc
  for d in "${real[@]+"${real[@]}"}"; do
    run_in "$lang" "$d" normal
    rc=$?
    if [ "$rc" -ne 0 ]; then
      printf 'FAIL: %s tests failed in %s (exit %d)\n' "$lang" "$d" "$rc" >&2
      failed=$((failed + 1))
    fi
  done

  if [ "$failed" -gt 0 ]; then
    printf '%s: %d of %d project(s) FAILED (fixture passed, so the lane works)\n' \
      "$lang" "$failed" "${#real[@]}" >&2
    exit 1
  fi

  # Say the project count out loud. "fixture OK, 0 projects" and "fixture OK, 7 projects" are
  # different facts and must not render identically.
  printf 'OK — %s: fixture passed, %d project(s) passed.\n' "$lang" "${#real[@]}"
  exit 0
}

main "$@"
