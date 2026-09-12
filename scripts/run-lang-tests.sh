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

# resolve_fixture(): each lane's fixture is its golden path by default; the WEYLAND_LANG_FIXTURE_DIR
# override keeps the <dir>/<lang> seam the bats guards inject through. See scripts/lib/lang-fixtures.sh.
# shellcheck source=scripts/lib/lang-fixtures.sh
. "$REPO_ROOT/scripts/lib/lang-fixtures.sh"

# Overridable for tests. The fixture tree is ALWAYS excluded from real-project discovery so it is
# never double-counted as production code.
FIXTURE_DIR="${WEYLAND_LANG_FIXTURE_DIR:-$REPO_ROOT/tests/lang}"
SCAN_ROOT="${WEYLAND_LANG_SCAN_ROOT:-$REPO_ROOT}"

LANGS="python shell java go rust dotnet kotlin scala php ruby elixir clojure cpp c erlang julia lua swift dart r perl haskell ada typescript javascript react nextjs react-native flutter swift-tokamak"

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
    dotnet)                            echo "dotnet" ;;
    kotlin)                            echo "gradle" ;;
    scala)                             echo "sbt" ;;
    php)                               echo "composer" ;;   # the on-PATH toolchain entry; it installs phpunit (vendor-local)
    ruby)                              echo "bundle" ;;     # the on-PATH toolchain entry; it installs rake/minitest (bundle-local)
    elixir)                            echo "mix" ;;
    clojure)                           echo "lein" ;;
    cpp|c)                             echo "cmake" ;;
    erlang)                            echo "rebar3" ;;
    julia)                             echo "julia" ;;
    lua)                               echo "busted" ;;
    swift)                             echo "swift" ;;
    dart)                              echo "dart" ;;
    r)                                 echo "Rscript" ;;
    perl)                              echo "prove" ;;
    haskell)                           echo "cabal" ;;
    ada)                               echo "alr" ;;
    typescript|javascript|react|nextjs) echo "node" ;;
    react-native)                      echo "npm" ;;    # B164 mobile CLIENT: jest-expo via `npm test`
    flutter)                           echo "flutter" ;; # B164 mobile CLIENT: `flutter test`
    swift-tokamak)                     echo "carton" ;;  # B164 "Swift w/o iOS": Tokamak→Wasm via carton
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
    dotnet)                            echo "*Tests.cs" ;;
    kotlin)                            echo "*Test.kt" ;;
    scala)                             echo "*Test.scala" ;;
    php)                               echo "*Test.php" ;;
    ruby)                              echo "*_test.rb" ;;
    elixir)                            echo "*_test.exs" ;;
    clojure)                           echo "*_test.clj" ;;
    cpp)                               echo "*_test.cpp" ;;
    c)                                 echo "*_test.c" ;;
    erlang)                            echo "*_tests.erl" ;;
    julia)                             echo "runtests.jl" ;;
    lua)                               echo "*_spec.lua" ;;
    swift)                             echo "*Tests.swift" ;;
    dart)                              echo "*_test.dart" ;;
    r)                                 echo "test-*.R" ;;
    perl)                              echo "*.t" ;;
    haskell)                           echo "*.hs" ;;   # any .hs resolves up to the one *.cabal root (the fixture); discovers "tests exist here"
    ada)                               echo "*_tests.adb" ;;
    typescript|javascript|react|nextjs) echo "*.test.js *.test.ts *.test.jsx *.test.tsx" ;;
    # B164 mobile CLIENTS need globs DISTINCT from the service lanes they would otherwise collide
    # with. react-native shares package.json + *.test.tsx with the node lanes, so its test file is
    # named *.rn.test.tsx (still matched by jest's default *.test.tsx discovery) and this glob keys
    # on that infix — otherwise the react-native lane would discover vite-react/nextjs/remix and run
    # jest on them as if they were Expo apps. flutter's widget_test.dart is already distinct from the
    # dart golden path's contract_test.dart, so `flutter test` never targets the dart/shelf service.
    react-native)                      echo "*.rn.test.tsx" ;;
    flutter)                           echo "widget_test.dart" ;;
    # swift-tokamak shares Package.swift with the swift lane; its test files carry a `.tokamak.swift`
    # infix (distinct from swift's `*Tests.swift`) so `carton test` never targets vapor/swift-ios and
    # `swift test` never targets this wasm-only client (which fails natively — Tokamak's GTK fallback).
    swift-tokamak)                     echo "*.tokamak.swift" ;;
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
    dotnet)                            echo "*.sln" ;;   # the solution at the service root (glob — name varies); resolve_root handles it
    kotlin)                            echo "settings.gradle.kts" ;;   # marks the Gradle project root
    scala)                             echo "build.sbt" ;;   # marks the sbt project root
    php)                               echo "composer.json" ;;   # marks the composer project root
    ruby)                              echo "Gemfile" ;;         # marks the bundler project root
    elixir)                            echo "mix.exs" ;;         # marks the mix project root
    clojure)                           echo "project.clj" ;;     # marks the Leiningen project root
    cpp|c)                             echo "CMakeLists.txt" ;;  # marks the CMake project root
    erlang)                            echo "rebar.config" ;;   # marks the rebar3 project root
    julia)                             echo "Project.toml" ;;   # marks the Julia project root
    lua)                               echo ".busted" ;;        # marks the busted project root
    swift)                             echo "Package.swift" ;;  # marks the SwiftPM package root
    dart)                              echo "pubspec.yaml" ;;   # marks the Dart package root
    r)                                 echo "plumber.R" ;;      # marks the plumber service root
    perl)                              echo "cpanfile" ;;       # marks the cpanm project root
    haskell)                           echo "*.cabal" ;;        # the cabal package root (glob — name varies; resolve_root handles it)
    ada)                               echo "alire.toml" ;;     # marks the Alire crate root
    typescript|javascript|react|nextjs) echo "package.json" ;;
    react-native)                      echo "package.json" ;;   # Expo app root (mobile CLIENT)
    flutter)                           echo "pubspec.yaml" ;;   # Flutter package root (mobile CLIENT)
    swift-tokamak)                     echo "Package.swift" ;;  # SwiftPM package root (Tokamak/Wasm CLIENT)
    python|shell)                      echo "" ;;   # resolved structurally, see resolve_root
    *)                                 return 1 ;;
  esac
}

# resolve_root <lang> <test-file> -> the directory the runner should execute in.
# Walks up from the test file toward SCAN_ROOT looking for the language's manifest. For python and
# shell there is no manifest: the root is the directory CONTAINING a `tests/` dir when the file sits
# under one (so pytest/bats run from the project and collect tests/), else the file's own directory.
resolve_root() {
  local lang="$1" file="$2" marker dir parent _m
  marker="$(root_marker_for "$lang")"
  dir="$(dirname "$file")"

  if [ -z "$marker" ]; then
    # python and shell both lack a manifest but need OPPOSITE roots, and conflating them was a real
    # bug: `pytest` runs from the PROJECT and collects `tests/`, while `bats` must run IN the
    # directory that holds the .bats files. Applying python's rule to shell resolved
    # `scripts/tests` -> `scripts`, where `bats .` finds nothing and exits 1 — a healthy suite
    # reported as an estate defect.
    if [ "$lang" = python ]; then
      case "$dir" in
        */tests|*/test) dirname "$dir"; return 0 ;;
      esac
    fi
    printf '%s\n' "$dir"; return 0
  fi

  while [ -n "$dir" ] && [ "$dir" != "/" ] && [ "$dir" != "." ]; do
    # The marker may be a literal filename (pom.xml, go.mod) OR a glob (dotnet's `*.sln`, whose name
    # varies per project). `find -name` does the pattern match ITSELF, so it handles both AND survives the
    # `set -f` this runs under (discover_roots disables shell globbing) — a shell glob would never expand.
    if [ -n "$(find "$dir" -maxdepth 1 -name "$marker" 2>/dev/null | head -1)" ]; then
      printf '%s\n' "$dir"; return 0
    fi
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
    # Elixir's fetched deps (deps/) and compiled output (_build/) are the mix analogues of
    # node_modules/target — both carry the DEPENDENCIES' own *_test.exs files. Without this, once a
    # lane runs `mix deps.get` (the CI lane runs --self-check, which does, before the normal run),
    # discovery finds e.g. deps/phoenix_pubsub/test/*_test.exs, treats the dep as a project, runs its
    # suite standalone, and reports a dependency's tests as an estate failure.
    */deps/*|*/_build/*)
      return 0 ;;
    # SwiftPM's `.build/` is the Swift analogue of node_modules/target/deps: `swift build`/`swift test`
    # clone every dependency into `.build/checkouts/<dep>` (vapor pulls swift-nio, async-http-client, …),
    # each a real package with its own `*Tests.swift`. Without this, once the FIXTURE builds (the lane
    # runs --self-check before the normal pass, and CI runs both), discovery descends into those
    # checkouts and reports ~30 dependency "projects" — several of whose standalone suites fail — as
    # estate defects. Note the leading dot: `*/build/*` above does NOT match `/.build/`.
    */.build/*)
      return 0 ;;
    # A `selfcheck/` dir is NEVER a standalone project — it is the deliberately-failing companion, run
    # only in --self-check mode from its owning project's dir. Under the fixture tree it is already
    # excluded (the whole tree is); this also covers golden-paths/<lang>/<fw>/selfcheck (B153).
    */selfcheck/*)
      return 0 ;;
    # The coding-agent eval harness (B104) ships task FIXTURES under eval/coding-agents/tasks/<id>/ —
    # deliberately-buggy code + a "Red" test designed to FAIL + a solution/. Those test_*.py / *_test.*
    # files are fixtures, NOT real projects; discovering them runs a test built to fail and reds the lane
    # (test-python failed exactly this way, 2026-09-10). Same rationale as selfcheck/.
    */eval/coding-agents/*)
      return 0 ;;
    # B164 mobile CLIENTS. react-native (package.json + *.test.tsx) and flutter (pubspec.yaml +
    # *_test.dart) share their manifests with the node and dart SERVICE lanes; without this the dart
    # lane would run `dart test` on the Flutter app and the node lanes would run `npm test` on the
    # Expo app, each in the wrong toolchain. Their own lanes run the fixture directly (resolve_fixture
    # always runs it), so excluding the tree from cross-repo discovery loses no coverage. NOTE:
    # swift-ios is deliberately NOT excluded — it rides the swift lane's discovery cleanly
    # (Package.swift + *Tests.swift, no collision) and must keep being found there.
    */golden-paths/mobile/react-native/*|*/golden-paths/mobile/flutter/*)
      return 0 ;;
    # swift-tokamak (Tokamak→Wasm) shares Package.swift with the swift lane; exclude it so `swift test`
    # never targets this wasm-only client (it fails natively — Tokamak's GTK fallback needs gtk.h). Its
    # own lane runs the fixture directly via resolve_fixture. swift-ios stays discoverable by the swift lane.
    */golden-paths/mobile/swift-tokamak/*)
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
  # `set -f` IS LOAD-BEARING. Without it the unquoted `$(test_glob_for ...)` below undergoes
  # PATHNAME EXPANSION against the current directory: run from the repo root, `*.bats` matches
  # nothing and survives as the literal pattern find needs; run from `scripts/tests`, it expands
  # into the real filenames there and discovery silently finds ZERO projects. Same code, correct or
  # broken purely by cwd — and it read as a clean "projects: 0" rather than an error.
  local restore_glob=0
  case "$-" in *f*) : ;; *) restore_glob=1; set -f ;; esac
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
  [ "$restore_glob" -eq 1 ] && set +f
  return 0
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

  # THE selfcheck/ CONVENTION. Every fixture keeps its deliberately-failing test in a `selfcheck/`
  # subdirectory, and NORMAL mode excludes that directory explicitly. Without this, each runner's
  # default discovery (`bats .`, `go test ./...`, `cargo test`, `node --test`) would collect the
  # deliberate failure and the fixture could never pass — the lane would report itself broken
  # forever. Excluding by directory beats filtering by test name: a name filter silently stops
  # matching when someone renames a test, and it would fail OPEN (the deliberate test quietly stops
  # running, and --self-check starts proving nothing).
  case "$lang" in
    python)
      # Per-project test deps, the python analogue of the node lane's `npm install`. A project whose
      # tests import beyond the CI image's baseline (weyland-dagster needs pyarrow/pandas) declares
      # them in requirements-test.txt — NOT its full runtime requirements.txt, which would drag the
      # whole dagster/torch stack into this fast lane. weyland-guard has none, so nothing installs and
      # its behaviour is unchanged. A failed install means the lane could not do its job: exit 2 (lane
      # broken), never a silent pass and never exit 1 (which would frame a deps gap as an estate defect).
      if [ -f "$dir/requirements-test.txt" ]; then
        (cd "$dir" && pip install --quiet --no-cache-dir -r requirements-test.txt) || {
          printf 'LANE BROKEN: pip install -r requirements-test.txt failed in %s\n' "$dir" >&2; return 2; }
      fi
      if [ "$mode" = selfcheck ]; then (cd "$dir" && pytest -q -p no:cacheprovider selfcheck)
      else (cd "$dir" && pytest -q -p no:cacheprovider --ignore=selfcheck); fi ;;
    shell)
      if [ "$mode" = selfcheck ]; then (cd "$dir" && bats selfcheck)
      else (cd "$dir" && bats .); fi ;;
    java)
      # Structural, like every other lane: Surefire excludes **/selfcheck/** by default and the
      # `selfcheck` profile inverts that to run ONLY it. A -Dtest=!Name filter would fail OPEN on a
      # rename, quietly retiring the deliberate test.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && mvn -q -B -Pselfcheck test)
      else (cd "$dir" && mvn -q -B test); fi ;;
    go)
      # The deliberate test sits behind a build tag, so a plain `go test ./...` cannot see it.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && go test -tags deliberate -run DeliberateFailure ./...)
      else (cd "$dir" && go test -race -coverprofile=coverage.out ./...); fi ;;
    rust)
      # #[ignore] keeps it out of a normal run; --ignored is the only way to reach it.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && cargo test -- --ignored)
      else (cd "$dir" && cargo test); fi ;;
    dotnet)
      # The deliberate test carries the `Category=selfcheck` trait; the normal run filters it OUT and the
      # self-check runs ONLY it. A trait filter (not a test-NAME filter) does not fail open on a rename —
      # dropping the trait makes the deliberate test run in the NORMAL lane, which is loud, not silent.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && dotnet test --nologo --filter 'Category=selfcheck')
      else (cd "$dir" && dotnet test --nologo --filter 'Category!=selfcheck'); fi ;;
    kotlin)
      # The deliberate test carries the JUnit `selfcheck` tag; build.gradle.kts excludes it from a normal
      # `gradle test` and includes ONLY it under -Pselfcheck. Tag-based, so a rename cannot silently retire it.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && gradle --no-daemon -q test -Pselfcheck)
      else (cd "$dir" && gradle --no-daemon -q test); fi ;;
    scala)
      # The deliberate test lives in a *Deliberate* class; build.sbt's Tests.Filter excludes it from a
      # normal `sbt test` and includes ONLY it under -Dselfcheck=true. Fail-closed on a rename (see build.sbt).
      if [ "$mode" = selfcheck ]; then (cd "$dir" && sbt -batch -Dselfcheck=true test)
      else (cd "$dir" && sbt -batch test); fi ;;
    php)
      # composer brings phpunit (dev); the deliberate test carries the PHPUnit `selfcheck` group, so a
      # normal run excludes it and the self-check runs ONLY it. Group-based → fail-closed on a rename.
      (cd "$dir" && composer install --no-interaction --no-progress -q) || {
        printf 'LANE BROKEN: composer install failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then (cd "$dir" && vendor/bin/phpunit --group selfcheck)
      else (cd "$dir" && vendor/bin/phpunit --exclude-group selfcheck); fi ;;
    ruby)
      # bundle brings the gems (rake/minitest/rack-test); the deliberate test lives in selfcheck/ and is
      # OUTSIDE the `test` rake task's test/**/ glob, so a normal `rake test` never collects it and
      # `rake test:selfcheck` runs ONLY it. Directory-based → fail-closed on a rename (a renamed
      # deliberate test makes test:selfcheck collect nothing → the --self-check guard sees exit 0).
      (cd "$dir" && bundle install --quiet) || {
        printf 'LANE BROKEN: bundle install failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then (cd "$dir" && bundle exec rake test:selfcheck)
      else (cd "$dir" && bundle exec rake test); fi ;;
    elixir)
      # mix brings the deps; the deliberate test carries @tag :selfcheck (excluded by test_helper).
      (cd "$dir" && mix deps.get >/dev/null 2>&1) || {
        printf 'LANE BROKEN: mix deps.get failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then
        # FAIL-CLOSED, and deliberately stronger than a bare exit check: `mix test --only <tag>` exits
        # non-zero BOTH when the tagged test fails AND when ZERO tests match (a renamed/removed
        # deliberate test) — so the exit code alone cannot tell "the guard worked" from "the guard's
        # own test vanished". Assert the REASON: require evidence a test actually FAILED ("N failure"
        # with N>=1). No failing test ran -> return 0 so the generic --self-check reports LANE BROKEN.
        # (project.md: assert the failure reason, not just the status.)
        local out
        out="$(cd "$dir" && mix test --only selfcheck 2>&1)"
        printf '%s\n' "$out" | tail -4
        printf '%s' "$out" | grep -qE '[1-9][0-9]* failure' && return 1 || return 0
      else
        (cd "$dir" && mix test)
      fi ;;
    clojure)
      # lein resolves deps into ~/.m2, NOT the repo tree, so there is no deps-leak like elixir's deps/
      # (and compiled output under target/ is already excluded by is_excluded). The deliberate test
      # carries ^:selfcheck; the :default test-selector (project.clj) excludes it from a normal run and
      # `lein test :selfcheck` runs ONLY it. Fail-closed on a rename: a removed/renamed tag makes
      # :selfcheck match zero tests -> "Ran 0 tests" -> exit 0 -> the --self-check guard reports LANE
      # BROKEN (verified: lein test with 0 tests run exits 0).
      if [ "$mode" = selfcheck ]; then (cd "$dir" && lein test :selfcheck)
      else (cd "$dir" && lein test); fi ;;
    cpp)
      # cmake configure + build the doctest binary (FetchContent pulls cpp-httplib + doctest into
      # build/_deps, which is_excluded skips via */build/*). The deliberate test lives in the doctest
      # "selfcheck" suite; normal excludes it, selfcheck runs ONLY it. Fail-closed on a rename: a removed
      # suite makes --test-suite=selfcheck match zero cases -> doctest exits 0 -> the guard reports LANE BROKEN.
      (cd "$dir" && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release >/dev/null 2>&1 && cmake --build build --target unit_tests >/dev/null) || {
        printf 'LANE BROKEN: cmake build failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then (cd "$dir" && ./build/unit_tests --test-suite=selfcheck)
      else (cd "$dir" && ./build/unit_tests --test-suite-exclude=selfcheck); fi ;;
    c)
      # cmake configure + build the assert-harness test binary. The `--selfcheck` arg triggers the
      # deliberate failure; fail-closed on a rename: without that branch, --selfcheck falls through to
      # the passing checks (exit 0) -> the guard reports LANE BROKEN.
      (cd "$dir" && cmake -S . -B build >/dev/null 2>&1 && cmake --build build --target unit_tests >/dev/null) || {
        printf 'LANE BROKEN: cmake build failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then (cd "$dir" && ./build/unit_tests --selfcheck)
      else (cd "$dir" && ./build/unit_tests); fi ;;
    erlang)
      # rebar3 fetches deps on demand. The deliberate test runs ONLY under the `selfcheck` profile
      # (rebar.config names it via eunit_tests), so a normal `rebar3 eunit` excludes it; the selfcheck
      # run executes exactly that module and asserts the failure reason — fail-closed on a rename.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && rebar3 as selfcheck eunit)
      else (cd "$dir" && rebar3 eunit); fi ;;
    julia)
      # Pkg.test() instantiates the test env. The deliberate test is env-gated (GOLDEN_SELFCHECK=1),
      # excluded from a normal run; selfcheck sets the env so it runs and fails.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && GOLDEN_SELFCHECK=1 julia --project=. -e 'using Pkg; Pkg.test()')
      else (cd "$dir" && julia --project=. -e 'using Pkg; Pkg.test()'); fi ;;
    lua)
      # busted reads .busted (default task excludes #selfcheck); the selfcheck task selects ONLY the
      # tagged deliberate spec. busted exits non-zero on a zero-tag match too → fail-closed on a rename.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && busted --run=selfcheck)
      else (cd "$dir" && busted); fi ;;
    swift)
      # swift test compiles + runs. The deliberate test is env-gated (GOLDEN_SELFCHECK=1) in its own
      # target, so a normal `swift test` skips it; selfcheck sets the env + filters to it so it fails.
      # SWIFT_BUILD_JOBS (set by the CI lane) caps build parallelism so the compile's PEAK memory stays
      # bounded on the RAM-tight CI node: a full-parallelism vapor build (BoringSSL/swift-crypto C++ + asm,
      # ~1057 units) OOM-killed the best-effort step pod mid-compile (#121). Unset locally → default speed.
      local jflag=""; [ -n "${SWIFT_BUILD_JOBS:-}" ] && jflag="-j ${SWIFT_BUILD_JOBS}"
      if [ "$mode" = selfcheck ]; then (cd "$dir" && GOLDEN_SELFCHECK=1 swift test $jflag --filter SelfCheckTests)
      else (cd "$dir" && swift test $jflag); fi ;;
    dart)
      # dart pub get resolves deps. The deliberate test is @Tags(['selfcheck']) + skipped via
      # dart_test.yaml, so a normal `dart test` excludes it; selfcheck needs `-t selfcheck --run-skipped`
      # (bare `-t selfcheck` reports "all skipped" / exit 0 — a fail-open trap) to force it to run + fail.
      (cd "$dir" && dart pub get >/dev/null 2>&1) || {
        printf 'LANE BROKEN: dart pub get failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then (cd "$dir" && dart test -t selfcheck --run-skipped)
      else (cd "$dir" && dart test); fi ;;
    r)
      # install the runtime + test packages if absent (rocker's PPM serves binaries) — the R analogue of
      # dart pub get. testthat::test_dir defaults stop_on_failure=TRUE → non-zero exit on a real failure.
      # The deliberate test is env-gated (GOLDEN_SELFCHECK=1); a normal run registers it as an empty skip.
      (cd "$dir" && Rscript -e 'p<-c("plumber","jsonlite","testthat"); m<-p[!p %in% rownames(installed.packages())]; if(length(m)) install.packages(m)' >/dev/null 2>&1) || {
        printf 'LANE BROKEN: R package install failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then (cd "$dir" && GOLDEN_SELFCHECK=1 Rscript -e 'testthat::test_dir("tests")')
      else (cd "$dir" && Rscript -e 'testthat::test_dir("tests")'); fi ;;
    perl)
      # cpanm brings Mojolicious (+Test::Mojo); the deliberate test lives in selfcheck/ (outside t/), so a
      # bare `prove -l` never collects it. Directory-based → fail-closed on a rename.
      (cd "$dir" && cpanm --quiet --notest --installdeps .) || {
        printf 'LANE BROKEN: cpanm --installdeps failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then (cd "$dir" && prove -l selfcheck/)
      else (cd "$dir" && prove -l); fi ;;
    haskell)
      # cabal fetches + builds deps (GHC — slow on a cold graph). The selfcheck suite is buildable only
      # under -fselfcheck (buildable: False otherwise), so a normal `cabal test contract` never builds it.
      # Flag-gated → fail-closed (dropping the flag makes selfcheck unbuildable, loud not silent).
      if [ "$mode" = selfcheck ]; then (cd "$dir" && cabal test selfcheck -fselfcheck)
      else (cd "$dir" && cabal test contract); fi ;;
    ada)
      # alr build compiles both mains (server + test_runner); the deliberate test is registered ONLY when
      # --selfcheck is passed (Test_Config gate before the suite builds), so a bare ./bin/test_runner never
      # runs it. Flag-gated → fail-closed.
      (cd "$dir" && alr -n build) || {
        printf 'LANE BROKEN: alr build failed in %s\n' "$dir" >&2; return 2; }
      if [ "$mode" = selfcheck ]; then (cd "$dir" && ./bin/test_runner --selfcheck)
      else (cd "$dir" && ./bin/test_runner); fi ;;
    react-native)
      # B164 mobile CLIENT (Expo + jest-expo). npm install if node_modules absent (fail closed, like
      # the node lane). The deliberate test lives in selfcheck/ and is excluded from a normal run by
      # the package.json `test` script's --testPathIgnorePatterns; `test:selfcheck` targets ONLY it,
      # so a normal run passes and selfcheck forces the failure. Directory-based → fail-closed on a rename.
      if [ ! -d "$dir/node_modules" ]; then
        (cd "$dir" && npm install --no-audit --no-fund --loglevel=error) || {
          printf 'LANE BROKEN: npm install failed in %s\n' "$dir" >&2; return 2; }
      fi
      if [ "$mode" = selfcheck ]; then (cd "$dir" && npm run --silent test:selfcheck)
      else (cd "$dir" && npm test --silent); fi ;;
    flutter)
      # B164 mobile CLIENT. `flutter test` resolves deps + compiles + runs widget tests. The deliberate
      # test is skip-tagged (dart_test.yaml) so a bare `flutter test` passes; selfcheck needs
      # `-t selfcheck --run-skipped` (bare `-t selfcheck` reports "all skipped"/exit 0 — the same
      # package:test fail-open trap as dart/shelf) to force it to run and fail.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && flutter test -t selfcheck --run-skipped)
      else (cd "$dir" && flutter test); fi ;;
    swift-tokamak)
      # B164 "Swift without iOS": Tokamak (SwiftUI-compatible) → WebAssembly via carton. Tests run as
      # wasm XCTest in Node.js (`--environment node`, headless — no browser, no GTK). The deliberate test
      # is compile-flag-gated: a normal run compiles its body away (passes); selfcheck adds
      # `-Xswiftc -DSELFCHECK` so it fails. FAIL-CLOSED — remove the `#if SELFCHECK` block and the
      # selfcheck run stops failing, which the --self-check guard reports as LANE BROKEN.
      if [ "$mode" = selfcheck ]; then (cd "$dir" && carton test --environment node -Xswiftc -DSELFCHECK)
      else (cd "$dir" && carton test --environment node); fi ;;
    typescript|javascript|react|nextjs)
      # TWO NODE SHAPES, ONE RUNNER. A project that declares its own `test` script owns how its
      # tests run (React and Next.js need jest + a DOM, which node's built-in runner cannot
      # provide); anything else uses `node --test` directly and stays dependency-free. Honouring
      # package.json is also what makes this work for real projects, which will always have one.
      if [ -f "$dir/package.json" ] && node -e \
           'process.exit(require("./package.json").scripts?.test?0:1)' \
           --input-type=commonjs >/dev/null 2>&1 \
         || (cd "$dir" && node -e 'const p=require("./package.json");process.exit(p.scripts&&p.scripts.test?0:1)' 2>/dev/null); then
        # Dependencies must exist before jest can run. Install only when absent — a real CI cache
        # makes this a no-op on the common path (roadie's pattern: named cache volume + skip).
        if [ ! -d "$dir/node_modules" ]; then
          (cd "$dir" && npm install --no-audit --no-fund --loglevel=error) || {
            printf 'LANE BROKEN: npm install failed in %s\n' "$dir" >&2; return 2; }
        fi
        if [ "$mode" = selfcheck ]; then (cd "$dir" && npm run --silent test:selfcheck)
        else (cd "$dir" && npm test --silent); fi
      else
        # A `node --test` project is NOT automatically dependency-free — Fastify uses node:test yet
        # requires the `fastify` module at load time. Install exactly as the jest branch (and
        # scan_node) do: package.json present + node_modules absent → npm install, fail closed.
        # Without this the test loads MODULE_NOT_FOUND in a fresh CI clone (node_modules gitignored).
        if [ -f "$dir/package.json" ] && [ ! -d "$dir/node_modules" ]; then
          (cd "$dir" && npm install --no-audit --no-fund --loglevel=error) || {
            printf 'LANE BROKEN: npm install failed in %s\n' "$dir" >&2; return 2; }
        fi
        # node --test recurses and has NO path-exclusion flag (only --test-skip-pattern, which
        # matches test NAMES). So exclusion is structural: the deliberate file is named
        # *.selfcheck.* and does not match node's default *.test.* discovery glob. A name filter
        # would fail OPEN on a rename — the deliberate test would quietly stop running and the
        # self-check mode would start proving nothing.
        if [ "$mode" = selfcheck ]; then (cd "$dir" && node --test ./selfcheck/*.selfcheck.*)
        else (cd "$dir" && node --test); fi
      fi ;;
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

  local fixture; fixture="$(resolve_fixture "$lang" "$REPO_ROOT")"

  # THE FIXTURE IS MANDATORY. Its absence is a broken lane, never "nothing to do" — that
  # distinction is the whole reason fixtures exist.
  [ -d "$fixture" ] || die "LANE BROKEN: no $lang fixture at $fixture
The fixture is what proves this lane can run at all; without it a pass would mean nothing."

  # Real project roots, with the fixture removed so it is counted once, as the fixture. Two exclusions:
  # the tests/lang tree (the override seam + the shell fixture) and the resolved fixture itself — the
  # golden path serving as this lane's fixture lives OUTSIDE tests/lang, so it needs its own skip.
  local -a real=()
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    case "$d" in "$FIXTURE_DIR"|"$FIXTURE_DIR"/*) continue ;; esac
    [ "$d" = "$fixture" ] && continue
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
    # A COLLECTION error is not a failing test — nothing ran. pytest exits 1 for real failures but
    # 2/3/4 for collection, internal and usage errors; flattening those into "estate defect" makes
    # a missing dependency read as broken code. Found on the real tree: weyland-guard could not be
    # collected because prometheus_client was absent, and the lane blamed the code.
    # pytest exit 5 = "no tests collected". Discovery matched this path, so something here LOOKS
    # like a test and is not one. Found on the real tree: scripts/test_gateway_guardrails.py was a
    # standalone diagnostic script whose name matched the glob (renamed to verify_* by B88).
    # Skipping it quietly would be
    # absence-as-success; name the path so it gets renamed or excluded on purpose.
    if [ "$lang" = python ] && [ "$rc" -eq 5 ]; then
      printf 'LANE BROKEN: %s discovered %s but pytest collected NO TESTS there (exit 5).\n' \
        "$lang" "$d" >&2
      printf 'Either it is not a test suite (rename it) or discovery is matching the wrong thing.\n' >&2
      exit 2
    fi
    if [ "$lang" = python ] && { [ "$rc" -eq 2 ] || [ "$rc" -eq 3 ] || [ "$rc" -eq 4 ]; }; then
      printf 'LANE BROKEN: %s tests in %s could not be COLLECTED (pytest exit %d) — a missing\n' \
        "$lang" "$d" "$rc" >&2
      printf 'dependency or a usage error, not a failing test. Nothing was actually run.\n' >&2
      exit 2
    fi
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
