#!/usr/bin/env bash
#
# run-lang-scan.sh — per-language SCANNERS (B88 Phase 2). The analysis sibling of run-lang-tests.sh.
#
# WHY THIS EXISTS SEPARATELY FROM THE SCAN-SUITE. weyland deliberately splits execution from
# analysis: run-lang-tests.sh runs tests, services/scan-suite/scan.py runs analysis. That split is
# kept. What could NOT be kept was putting every language's scanners in the scan-suite's single
# image — it already carries python + a full Go toolchain + a JRE, and adding Rust, Java and Node
# toolchains would roughly triple it. Oversized layers have already broken builds in this repo with
# `unpigz: invalid deflate` (memory buildkit-large-layer-corruption). So the toolchain-heavy
# scanners run here, in the same pinned per-language images the test lanes use, and the registry
# marks them `runner: lang-scan`.
#
# THE REGISTRY IS THE SOURCE OF TRUTH. Every tool below is declared in repo-root quality-tools.yaml,
# and scripts/check-quality-tools.sh fails if this script and the registry disagree in EITHER
# direction. A tool that exists only as a registry line is documentation, not coverage — which is
# precisely the finding B88 Phase 3 records about syft/cosign/SLSA.
#
# FINDINGS DO NOT FAIL THE BUILD; A BROKEN LANE DOES.
#   0  the scanners ran (their findings are reported as counts, like the scan-suite)
#   2  the lane could not do its job — missing toolchain, unknown language, no projects resolvable
# Gating CI on lint counts turns every nit into a merge blocker and gets the gate muted, which is
# the same argument this repo makes about permanently-lit alerts. Counts go to the report; only an
# inability to LOOK is a failure.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/lang-fixtures.sh
. "$REPO_ROOT/scripts/lib/lang-fixtures.sh"   # resolve_fixture(): golden path by default (B153 switch)

LANGS="rust java dotnet kotlin scala php ruby elixir clojure cpp c erlang julia lua swift dart r perl haskell ada typescript javascript react nextjs react-native flutter"

die() { printf '%s\n' "$*" >&2; exit 2; }

# Findings are printed, never thrown. `run_tool <id> <root> <cmd...>` is also the exact token the
# drift guard greps for — keep the literal id as the first argument.
run_tool() {
  local id="$1" root="$2" req="$3"; shift 3
  # THE REQUIRED BINARY IS NAMED EXPLICITLY, not inferred from argv[0]. `cargo audit` and
  # `cargo deny` are SEPARATE binaries (cargo-audit, cargo-deny) invoked as cargo subcommands:
  # checking `cargo` finds the driver, the subcommand is still absent, and cargo exits 101 "no such
  # subcommand". That was reported as a FINDING (rc=101, 4 lines) rather than a broken lane —
  # a missing tool masquerading as a clean scan. Same for npx-dispatched node tools.
  if ! command -v "$req" >/dev/null 2>&1; then
    printf 'LANE BROKEN: %s needs `%s`, which is not on PATH (found via: %s)\n' "$id" "$req" "$1" >&2
    return 2
  fi
  local out rc tmp
  # THE TOOL'S OUTPUT AND ITS EXIT CODE ARE CAPTURED SEPARATELY, VIA A FILE — deliberately.
  # Piping into grep to strip noise and then reading ${PIPESTATUS[0]} does NOT work here: the
  # pipeline runs inside a command substitution, so PIPESTATUS in the outer shell describes the
  # ASSIGNMENT, not the tool. That silently produced `tsc rc=1` on a run with zero findings. It is
  # the same "$? after a pipeline is the LAST command's status" trap recorded in project.md, and it
  # has now appeared three times in this repo — including here, inside a fix for a different bug.
  #
  # npm also prints update notices to stderr on every invocation; those were being COUNTED as
  # findings, so a clean eslint run reported 8 lines. A count that includes the tool's own chatter
  # is not a measurement.
  tmp="$(mktemp)"
  (cd "$root" && npm_config_update_notifier=false NO_UPDATE_NOTIFIER=1 "$@" >"$tmp" 2>&1)
  rc=$?
  out="$(grep -vE '^npm (notice|warn)|^$' "$tmp" || true)"
  rm -f "$tmp"
  # `npx --no-install <tool>` exits non-zero with a "could not determine executable" style message
  # when the tool is absent. Left alone that reads as a FINDING (rc=1, 2 lines) — a missing scanner
  # reported as a clean scan, which is the same absence-as-success the cargo subcommands showed.
  # npm changes this message across majors: older npm printed `npm ERR! canceled`; current npm (11)
  # prints `npm error npx canceled due to missing packages and no YES option`. Matching only the old
  # strings failed OPEN on the new one — a missing eslint on a golden path read as `rc=1` findings
  # and the lane stayed green (B153). Match the stable phrase `npx canceled` too, and fail closed.
  case "$out" in
    *"could not determine executable"*|*"not found"*|*"npm ERR! canceled"*|*"npx canceled"*|*"missing packages and no YES option"*)
      printf 'LANE BROKEN: %s is not installed in %s (npx could not resolve it)\n' "$id" "$root" >&2
      return 2 ;;
  esac
  # A scanner's exit code is NOT its verdict — promtool exits 0 while printing FAILED, and this repo
  # has been bitten by that three separate times. Report the count and the status, and let the
  # reader see both.
  printf '  %-16s %-6s %s\n' "$id" "rc=$rc" "$(printf '%s' "$out" | grep -c . || true) line(s)"
  return 0
}

usage() { printf 'usage: run-lang-scan.sh <%s>\n' "$LANGS" >&2; exit 2; }

roots_for() {
  local lang="$1"
  bash "$REPO_ROOT/scripts/run-lang-tests.sh" "$lang" --list-roots 2>/dev/null \
    | sed -n 's/^project: //p'
}

scan_rust() {
  local root="$1"
  local rc=0
  run_tool clippy      "$root" cargo-clippy cargo clippy --all-targets -- -D warnings || rc=2
  run_tool rustfmt     "$root" rustfmt cargo fmt -- --check || rc=2
  run_tool cargo-audit "$root" cargo-audit cargo audit || rc=2
  run_tool cargo-deny  "$root" cargo-deny cargo deny check || rc=2
  return $rc
}

scan_dotnet() {
  local root="$1"
  local rc=0
  # `dotnet format` is the standard .NET style + analyzer gate. Run in $root it uses the solution
  # (golden.sln), so it covers App + tests. --verify-no-changes exits non-zero on a diff — an advisory
  # FINDING, not a broken lane; the lane fails (exit 2) only if `dotnet` itself is missing (fail-closed).
  run_tool dotnet-format "$root" dotnet dotnet format --verify-no-changes || rc=2
  return $rc
}

scan_erlang() {
  local root="$1"; local rc=0
  # rebar3 xref (built-in cross-reference static analysis) — no extra install. xref warnings are advisory
  # FINDINGS (rebar3 exits 0); the lane fails (exit 2) only if rebar3 itself is missing (fail-closed).
  run_tool xref "$root" rebar3 rebar3 xref || rc=2
  return $rc
}

scan_julia() {
  local root="$1"; local rc=0
  # JuliaFormatter (the de-facto Julia style tool; Pkg.add'd on demand). Format diffs are an advisory
  # FINDING; the lane fails (exit 2) only if julia itself is missing (fail-closed).
  run_tool juliaformatter "$root" julia julia -e 'using Pkg; Pkg.add(name="JuliaFormatter", version="1"); using JuliaFormatter; exit(format(".", overwrite=false) ? 0 : 1)' || rc=2
  return $rc
}

scan_lua() {
  local root="$1"; local rc=0
  # luacheck is the standard Lua linter (over lua/ + spec/). Warnings are advisory FINDINGS; the lane
  # fails (exit 2) only if luacheck itself is missing (fail-closed).
  run_tool luacheck "$root" luacheck luacheck . || rc=2
  return $rc
}

scan_swift() {
  local root="$1"; local rc=0
  # swift-format (bundled in the Swift 6 toolchain) lint over Sources + Tests. Style warnings are advisory
  # FINDINGS (lint exits 0); the lane fails (exit 2) only if swift itself is missing (fail-closed).
  run_tool swift-format "$root" swift swift format lint --recursive Sources Tests || rc=2
  return $rc
}

scan_dart() {
  local root="$1"; local rc=0
  # dart analyze — the standard Dart static analysis (analysis_options.yaml). Issues are advisory
  # FINDINGS; the lane fails (exit 2) only if dart itself is missing (fail-closed).
  run_tool dart-analyze "$root" dart dart analyze || rc=2
  return $rc
}

scan_r() {
  local root="$1"; local rc=0
  # lintr is an R PACKAGE (no standalone binary for run_tool's command-v to catch), so ensure it is
  # present here — fail-closed if the install fails; otherwise a missing lintr would read as a finding.
  (cd "$root" && Rscript -e 'if(!"lintr" %in% rownames(installed.packages())) install.packages("lintr")' >/dev/null 2>&1) || {
    printf 'LANE BROKEN: lintr install failed in %s\n' "$root" >&2; return 2; }
  run_tool lintr "$root" Rscript Rscript -e 'print(lintr::lint_dir("."))' || rc=2
  return $rc
}

scan_perl() {
  local root="$1"; local rc=0
  # perlcritic (Perl::Critic), the standard Perl static analyser; the scan-perl lane cpanm-installs it so
  # command-v perlcritic fails closed if absent. Violations are advisory FINDINGS.
  run_tool perlcritic "$root" perlcritic perlcritic lib script || rc=2
  return $rc
}

scan_haskell() {
  local root="$1"; local rc=0
  # hlint, the standard Haskell linter (the scan-haskell lane cabal-installs it; command-v hlint fails
  # closed if absent). Hints are advisory FINDINGS.
  run_tool hlint "$root" hlint hlint src app test || rc=2
  return $rc
}

scan_ada() {
  local root="$1"; local rc=0
  # No lightweight standard Ada linter ships in the toolchain (gnatcheck/libadalang-tools is a heavy
  # separate Alire crate), so the scan is the compiler's own -gnatwa (all warnings) + -gnaty (style),
  # enabled in the .gpr and surfaced by re-running the build. `alr` (command-v) fails closed; warnings
  # are advisory FINDINGS.
  # ADA_BUILD_JOBS (CI lane) caps gprbuild parallelism so the gnatcoll-from-source build stays within the
  # step pod's memory (same OOM class as test-ada, #124). Unset → default. ${VAR:+...} adds nothing if unset.
  run_tool gnat-warnings "$root" alr alr -n build ${ADA_BUILD_JOBS:+-- -j${ADA_BUILD_JOBS}} || rc=2
  return $rc
}

scan_reactnative() {
  local root="$1"; local rc=0
  # B164 mobile CLIENT (Expo). eslint over the app (eslint.config.mjs), like the node lane — reuse the
  # already-registered `eslint` tool id. npm install if node_modules absent so npx can resolve eslint
  # (fail closed). Lint findings are advisory; the lane fails (exit 2) only on a missing toolchain.
  [ -d "$root/node_modules" ] || (cd "$root" && npm install --no-audit --no-fund --loglevel=error) || {
    printf 'LANE BROKEN: npm install failed in %s\n' "$root" >&2; return 2; }
  run_tool eslint "$root" npx npx --no-install eslint . || rc=2
  return $rc
}

scan_flutter() {
  local root="$1"; local rc=0
  # B164 mobile CLIENT. `flutter analyze` is the standard Flutter static analysis (analysis_options.yaml
  # with flutter_lints). Issues are advisory FINDINGS; the lane fails (exit 2) only if flutter itself is
  # missing (fail-closed via run_tool's command-v probe).
  run_tool flutter-analyze "$root" flutter flutter analyze || rc=2
  return $rc
}

scan_kotlin() {
  local root="$1"
  local rc=0
  # ktlint (via the gradle plugin) is the standard Kotlin style/lint gate; over the project it checks main
  # + test. ktlintCheck exits non-zero on a violation — an advisory FINDING; the lane fails (exit 2) only
  # if gradle itself is missing (fail-closed).
  run_tool ktlint "$root" gradle gradle --no-daemon -q ktlintCheck || rc=2
  return $rc
}

scan_scala() {
  local root="$1"
  local rc=0
  # scalafmt (via the sbt-scalafmt plugin, `scalafmtCheckAll`) is the standard Scala style/format gate;
  # over the project it checks main + test. A format diff exits non-zero — an advisory FINDING; the lane
  # fails (exit 2) only if sbt itself is missing (fail-closed).
  run_tool scalafmt "$root" sbt sbt -batch scalafmtCheckAll || rc=2
  return $rc
}

scan_php() {
  local root="$1"
  local rc=0
  # composer brings phpstan (dev); install first (like scan_node's npm install), fail closed. Probe
  # `php` (on PATH) — phpstan lives at vendor/bin, so an absent phpstan is caught by run_tool's
  # output-based missing-detection ("not found"), not the PATH probe.
  (cd "$root" && composer install --no-interaction --no-progress -q) || {
    printf 'LANE BROKEN: composer install failed in %s\n' "$root" >&2; return 2; }
  run_tool phpstan "$root" php vendor/bin/phpstan analyse --no-progress || rc=2
  return $rc
}

scan_ruby() {
  local root="$1"
  local rc=0
  # bundle brings rubocop (test group); install first (like scan_php's composer install), fail closed.
  # Probe `ruby` (on PATH) — rubocop runs via `bundle exec`, so an absent rubocop is caught by run_tool's
  # output-based missing-detection ("command not found"), not the PATH probe.
  (cd "$root" && bundle install --quiet) || {
    printf 'LANE BROKEN: bundle install failed in %s\n' "$root" >&2; return 2; }
  run_tool rubocop "$root" ruby bundle exec rubocop || rc=2
  return $rc
}

scan_elixir() {
  local root="$1"
  local rc=0
  # mix brings credo (dev/test dep); fetch first (like scan_php's composer install), fail closed. Probe
  # `mix` (on PATH) — credo runs as `mix credo`, so an absent credo is caught by run_tool's output-based
  # missing-detection ("could not be found"), not the PATH probe.
  (cd "$root" && mix deps.get >/dev/null 2>&1) || {
    printf 'LANE BROKEN: mix deps.get failed in %s\n' "$root" >&2; return 2; }
  run_tool credo "$root" mix mix credo --strict || rc=2
  return $rc
}

scan_clojure() {
  local root="$1"
  local rc=0
  # clj-kondo is THE Clojure linter — a standalone binary. The scan-clojure CI step runs in the
  # cljkondo/clj-kondo image (binary present), so no install/fetch here; it lints src + test statically.
  # Probe `clj-kondo` — absent → run_tool's PATH probe fails closed (LANE BROKEN).
  run_tool clj-kondo "$root" clj-kondo clj-kondo --lint src test || rc=2
  return $rc
}

scan_cpp() {
  local root="$1"
  local rc=0
  # cppcheck is the C/C++ static analyzer (warning + style). It exits 0 even with findings (no
  # --error-exitcode), so only the finding COUNT is reported; the lane fails (exit 2) only if cppcheck
  # itself is missing (fail-closed). Lints src (the FetchContent deps under build/ are not scanned).
  run_tool cppcheck "$root" cppcheck cppcheck --enable=warning,style --quiet src || rc=2
  return $rc
}

# C shares the C/C++ analyzer; a separate function keeps the per-language dispatch uniform.
scan_c() { scan_cpp "$@"; }

scan_java() {
  # All four ride Maven plugins, so they need no separate install — `mvn <plugin>:check` resolves
  # them on first run. error-prone is a compiler plugin, hence `compile` rather than a goal.
  local root="$1"
  local rc=0
  run_tool spotbugs    "$root" mvn mvn -q -B com.github.spotbugs:spotbugs-maven-plugin:check || rc=2
  run_tool pmd         "$root" mvn mvn -q -B org.apache.maven.plugins:maven-pmd-plugin:check || rc=2
  run_tool checkstyle  "$root" mvn mvn -q -B org.apache.maven.plugins:maven-checkstyle-plugin:check || rc=2
  run_tool error-prone "$root" mvn mvn -q -B -Derror-prone.enabled=true compile || rc=2
  return $rc
}

scan_node() {
  local root="$1" rc=0
  [ -d "$root/node_modules" ] || (cd "$root" && npm install --no-audit --no-fund --loglevel=error) || {
    printf 'LANE BROKEN: npm install failed in %s\n' "$root" >&2; return 2; }
  run_tool eslint          "$root" npx npx --no-install eslint . || rc=2
  run_tool npm-audit       "$root" npm npm audit --audit-level=high || rc=2
  run_tool license-checker "$root" npx npx --no-install license-checker --summary || rc=2
  # tsc / next lint are CAPABILITY-driven, not lane-driven: the four node lanes share one repo-wide
  # discovery glob, so a plain-JS project (e.g. golden-paths/node/express) is discovered under the
  # typescript/react/nextjs lanes too. Gating on the lane would demand a tsconfig + Next on an Express
  # app; gating on what the project actually IS runs the right scanners wherever it is discovered.
  # A Next.js project is type-checked by `next build` and linted by `next lint`, never by bare tsc
  # (which needs next-env.d.ts + .next/types from a build); so tsc is for the non-Next TS projects.
  if [ -f "$root/tsconfig.json" ] && ! grep -q '"next"[[:space:]]*:' "$root/package.json" 2>/dev/null; then
    run_tool tsc "$root" npx npx --no-install tsc --noEmit || rc=2
  fi
  if [ -f "$root/package.json" ] && grep -q '"next"[[:space:]]*:' "$root/package.json"; then
    run_tool next-lint "$root" npx npx --no-install next lint || rc=2
  fi
  return $rc
}

main() {
  [ $# -ge 1 ] || usage
  local lang="$1"
  case " $LANGS " in *" $lang "*) : ;; *) die "unknown language: '$lang'
valid: $LANGS" ;; esac

  # The fixture is scanned too, exactly as the test lanes run it — it is what proves the scanners
  # can execute at all. It is the language's golden path (B153 switch); roots_for already excludes it
  # from the discovered real projects (run-lang-tests owns that), so it is scanned exactly once.
  local fixture; fixture="$(resolve_fixture "$lang" "$REPO_ROOT")"
  [ -d "$fixture" ] || die "LANE BROKEN: no $lang fixture at $fixture"

  local -a targets=("$fixture")
  local d
  while IFS= read -r d; do [ -n "$d" ] && targets+=("$d"); done < <(roots_for "$lang")

  printf 'scanning %s: %d target(s)\n' "$lang" "${#targets[@]}"
  local broken=0
  for d in "${targets[@]}"; do
    printf '%s\n' "$d"
    case "$lang" in
      rust) scan_rust "$d" || broken=1 ;;
      java) scan_java "$d" || broken=1 ;;
      dotnet) scan_dotnet "$d" || broken=1 ;;
      erlang) scan_erlang "$d" || broken=1 ;;
      julia) scan_julia "$d" || broken=1 ;;
      lua) scan_lua "$d" || broken=1 ;;
      swift) scan_swift "$d" || broken=1 ;;
      dart) scan_dart "$d" || broken=1 ;;
      r) scan_r "$d" || broken=1 ;;
      perl) scan_perl "$d" || broken=1 ;;
      haskell) scan_haskell "$d" || broken=1 ;;
      ada) scan_ada "$d" || broken=1 ;;
      react-native) scan_reactnative "$d" || broken=1 ;;
      flutter) scan_flutter "$d" || broken=1 ;;
      kotlin) scan_kotlin "$d" || broken=1 ;;
      scala) scan_scala "$d" || broken=1 ;;
      php) scan_php "$d" || broken=1 ;;
      ruby) scan_ruby "$d" || broken=1 ;;
      elixir) scan_elixir "$d" || broken=1 ;;
      clojure) scan_clojure "$d" || broken=1 ;;
      cpp) scan_cpp "$d" || broken=1 ;;
      c) scan_c "$d" || broken=1 ;;
      typescript|javascript|react|nextjs) scan_node "$d" || broken=1 ;;
    esac
  done

  [ "$broken" -eq 0 ] || exit 2
  printf 'OK — %s scanners ran over %d target(s). Findings are counts, not gates.\n' \
    "$lang" "${#targets[@]}"
}

main "$@"
