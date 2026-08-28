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
SCAN_ROOT="${WEYLAND_LANG_SCAN_ROOT:-$REPO_ROOT}"
FIXTURE_DIR="${WEYLAND_LANG_FIXTURE_DIR:-$REPO_ROOT/tests/lang}"

LANGS="rust java typescript javascript react nextjs"

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
  case "$out" in
    *"could not determine executable"*|*"not found"*|*"npm ERR! canceled"*)
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
  run_tool clippy      "$root" cargo-clippy cargo clippy --all-targets -- -D warnings
  run_tool rustfmt     "$root" rustfmt cargo fmt -- --check
  run_tool cargo-audit "$root" cargo-audit cargo audit
  run_tool cargo-deny  "$root" cargo-deny cargo deny check
}

scan_java() {
  # All four ride Maven plugins, so they need no separate install — `mvn <plugin>:check` resolves
  # them on first run. error-prone is a compiler plugin, hence `compile` rather than a goal.
  local root="$1"
  run_tool spotbugs    "$root" mvn mvn -q -B com.github.spotbugs:spotbugs-maven-plugin:check
  run_tool pmd         "$root" mvn mvn -q -B org.apache.maven.plugins:maven-pmd-plugin:check
  run_tool checkstyle  "$root" mvn mvn -q -B org.apache.maven.plugins:maven-checkstyle-plugin:check
  run_tool error-prone "$root" mvn mvn -q -B -Derror-prone.enabled=true compile
}

scan_node() {
  local root="$1" lang="$2"
  [ -d "$root/node_modules" ] || (cd "$root" && npm install --no-audit --no-fund --loglevel=error) || {
    printf 'LANE BROKEN: npm install failed in %s\n' "$root" >&2; return 2; }
  run_tool eslint          "$root" npx npx --no-install eslint .
  run_tool npm-audit       "$root" npm npm audit --audit-level=high
  run_tool license-checker "$root" npx npx --no-install license-checker --summary
  case "$lang" in
    typescript|react|nextjs) run_tool tsc "$root" npx npx --no-install tsc --noEmit ;;
  esac
  case "$lang" in
    nextjs) run_tool next-lint "$root" npx npx --no-install next lint ;;
  esac
}

main() {
  [ $# -ge 1 ] || usage
  local lang="$1"
  case " $LANGS " in *" $lang "*) : ;; *) die "unknown language: '$lang'
valid: $LANGS" ;; esac

  # The fixture is scanned too, exactly as the test lanes run it — it is what proves the scanners
  # can execute at all when a language has no production code yet (Rust today).
  local fixture="$FIXTURE_DIR/$lang"
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
      typescript|javascript|react|nextjs) scan_node "$d" "$lang" || broken=1 ;;
    esac
  done

  [ "$broken" -eq 0 ] || exit 2
  printf 'OK — %s scanners ran over %d target(s). Findings are counts, not gates.\n' \
    "$lang" "${#targets[@]}"
}

main "$@"
