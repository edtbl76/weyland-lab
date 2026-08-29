#!/usr/bin/env bash
#
# coverage-ratchet.sh — per-language coverage RATCHET (B88 gap #1).
#
# THE PROBLEM. Exactly one test lane (Go) writes a coverage profile, and nothing reads it — a number
# produced and discarded. Tests can rot to near-zero while CI stays green, which is the
# absence-as-success pattern the whole B88 effort exists to remove, sitting inside the test harness.
#
# WHY A RATCHET, NOT AN 80% FLOOR. A hard threshold on lanes that are mostly hello-world fixtures
# (Rust has no production code yet; Java is two Flink modules) either fails on day one or forces fake
# tests to pad the number — and coverage % is the metric that most invites gaming. A threshold that
# fires on honest low coverage gets muted, the same argument this repo keeps making about
# permanently-lit alerts. So the ratchet fails ONLY when coverage DROPS against a committed baseline:
# new untested code is caught, existing gaps are not a false alarm, and a number that only has to
# not-decrease cannot be gamed upward.
#
# USAGE
#   coverage-ratchet.sh run <lang>            run <lang>'s tests with coverage, ratchet every project
#   coverage-ratchet.sh compare <key> <pct> <baseline-file>   the pure ratchet step (unit-tested)
#   coverage-ratchet.sh --supports <lang>     exit 0 if a coverage extractor exists for <lang>
#
# EXIT CODES
#   0  coverage held or improved (baseline recorded/updated)
#   1  coverage REGRESSED against the baseline           -> a real finding
#   2  the ratchet could not run (missing tool, bad number, unknown language) -> broken lane
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCAN_ROOT="${WEYLAND_LANG_SCAN_ROOT:-$REPO_ROOT}"
FIXTURE_DIR="${WEYLAND_LANG_FIXTURE_DIR:-$REPO_ROOT/tests/lang}"
BASELINE_FILE="${WEYLAND_COVERAGE_BASELINE:-$REPO_ROOT/tests/lang/coverage-baseline.tsv}"

# A drop smaller than this (percentage points) is float noise, not a regression: `go tool cover` and
# pytest-cov round differently run to run. Small enough that a real one-test deletion still trips it.
TOLERANCE="0.1"

die() { printf '%s\n' "$*" >&2; exit 2; }

# is_number <s> — a bare decimal, nothing else. "N/A", "", "42%" all fail.
is_number() { case "$1" in ''|*[!0-9.]*) return 1 ;; *) return 0 ;; esac; }

# compare <key> <pct> <baseline-file> — THE PURE RATCHET. No toolchain, no I/O beyond the baseline.
compare() {
  local key="$1" pct="$2" file="$3" prev
  is_number "$pct" || die "RATCHET BROKEN: coverage for $key is not a number: '$pct'
An unparseable figure means extraction failed; treating it as 0 or as a skip would both lie."

  [ -f "$file" ] || : > "$file"
  prev="$(awk -F'\t' -v k="$key" '$1==k{print $2; exit}' "$file")"

  if [ -z "$prev" ]; then
    printf '%s\t%s\n' "$key" "$pct" >> "$file"
    printf 'baseline recorded: %s = %s%%\n' "$key" "$pct"
    return 0
  fi

  # drop = prev - pct ; regression when drop > TOLERANCE
  local regressed
  regressed="$(awk -v p="$prev" -v n="$pct" -v t="$TOLERANCE" 'BEGIN{print ((p-n)>t)?1:0}')"
  if [ "$regressed" = "1" ]; then
    printf 'COVERAGE REGRESSED: %s dropped %s%% -> %s%% (baseline held, not rewritten down)\n' \
      "$key" "$prev" "$pct" >&2
    return 1
  fi

  # held or improved — ratchet the baseline UP to the new figure when it rose.
  local rose
  rose="$(awk -v p="$prev" -v n="$pct" 'BEGIN{print (n>p)?1:0}')"
  if [ "$rose" = "1" ]; then
    local tmp; tmp="$(mktemp)"
    awk -F'\t' -v k="$key" -v n="$pct" 'BEGIN{OFS="\t"} $1==k{$2=n} {print}' "$file" > "$tmp"
    mv "$tmp" "$file"
    printf 'coverage improved: %s %s%% -> %s%% (baseline ratcheted up)\n' "$key" "$prev" "$pct"
  else
    printf 'coverage held: %s = %s%%\n' "$key" "$pct"
  fi
  return 0
}

# ── per-language coverage EXTRACTORS ─────────────────────────────────────────────────────────────
# Each runs the project's tests with coverage on and prints ONE total line-coverage percentage.
# Native where possible (no extra dependency); the few that need a tool name it so a missing one is
# a broken lane (exit 2), never a silent pass.
# supports <lang> — has a MEANINGFUL coverage extractor. Shell is deliberately absent: see
# EXCLUDED_SHELL below. Everything else in the test-lane set is ratcheted.
supports() { case "$1" in python|java|go|rust|typescript|javascript|react|nextjs) return 0 ;; *) return 1 ;; esac; }

# SHELL IS INTENTIONALLY NOT RATCHETED, and this is a decision, not an oversight.
#  (1) kcov (the only shell line-coverage tool) is not in Alpine repos, and the shell test lane runs
#      on bats/bats:latest (Alpine). It would need a separate image built solely for coverage.
#  (2) More fundamentally, line-coverage of a shell ORCHESTRATOR measures almost nothing here. These
#      scripts are tested by stubbing every external (git/gh/kubectl/...) and asserting the DECISION
#      the script reaches (see scripts/tests/helper.bash) — a script can be exhaustively tested at
#      modest line coverage, or hit high line coverage while asserting nothing. Forcing a kcov
#      toolchain onto the lane with the least-meaningful metric is effort chasing a number that lies.
# Excluded LOUDLY (a `run shell` says so) rather than silently skipped — a silent skip is the
# absence-as-success this whole ratchet exists to prevent.
is_excluded_shell() { [ "$1" = shell ]; }

need() { command -v "$1" >/dev/null 2>&1 || die "RATCHET BROKEN: $2 needs \`$1\`, not on PATH"; }

cov_go() { # <dir> -> total %
  need go go
  ( cd "$1" && go test -cover -coverprofile=/tmp/cov.out ./... >/dev/null 2>&1
    go tool cover -func=/tmp/cov.out 2>/dev/null | awk '/^total:/{gsub(/%/,"",$3); print $3}' )
}

cov_python() { # pytest-cov; term-report's TOTAL row
  need pytest pytest
  ( cd "$1" && pytest -q -p no:cacheprovider --ignore=selfcheck \
      --cov=. --cov-report=term-missing 2>/dev/null \
      | awk '/^TOTAL/{gsub(/%/,"",$NF); print $NF}' )
}

cov_node() { # node 22+ built-in coverage; parse the "all files" summary line
  need node node
  ( cd "$1" || return
    if [ -f package.json ] && node -e 'process.exit((require("./package.json").scripts||{}).test?0:1)' 2>/dev/null; then
      npm test --silent -- --coverage 2>/dev/null | awk -F'|' '/All files/{gsub(/ /,"",$2); print $2; exit}'
    else
      node --test --experimental-test-coverage 2>/dev/null \
        | awk '/all files/{for(i=1;i<=NF;i++) if($i ~ /^[0-9.]+$/){print $i; exit}}'
    fi )
}

cov_java() { # jacoco line-coverage from the CSV report (INSTRUCTION or LINE cols)
  need mvn mvn
  ( cd "$1" && mvn -q -B -Djacoco.skip=false org.jacoco:jacoco-maven-plugin:prepare-agent test \
       org.jacoco:jacoco-maven-plugin:report >/dev/null 2>&1
    local csv; csv="$(find . -name jacoco.csv -path '*/site/*' 2>/dev/null | head -1)"
    [ -f "$csv" ] || return 0
    awk -F, 'NR>1{miss+=$4; cov+=$5} END{ if((miss+cov)>0) printf "%.1f", cov*100/(miss+cov) }' "$csv" )
}

cov_rust() { # cargo-llvm-cov reports a TOTAL line %; the standard rust coverage tool
  need cargo cargo
  command -v cargo-llvm-cov >/dev/null 2>&1 || die "RATCHET BROKEN: rust coverage needs \`cargo-llvm-cov\` (cargo install cargo-llvm-cov)"
  ( cd "$1" && cargo llvm-cov --summary-only 2>/dev/null \
      | awk '/^TOTAL/{for(i=1;i<=NF;i++) if($i ~ /%$/){gsub(/%/,"",$i); print $i; exit}}' )
}


extract() { # extract <lang> <dir>
  case "$1" in
    go) cov_go "$2" ;;
    python) cov_python "$2" ;;
    typescript|javascript|react|nextjs) cov_node "$2" ;;
    java) cov_java "$2" ;;
    rust) cov_rust "$2" ;;
    *) return 1 ;;
  esac
}

# run <lang> — ratchet every discovered project (fixture + real), aggregate the verdict.
run_lang() {
  local lang="$1"
  if is_excluded_shell "$lang"; then
    printf 'shell: coverage NOT ratcheted by design — line-coverage of an orchestrator that is\n'
    printf 'tested by asserting decisions (stubbed externals) measures almost nothing. See the\n'
    printf 'EXCLUDED note in coverage-ratchet.sh. This is a deliberate skip, reported not hidden.\n'
    exit 0
  fi
  supports "$lang" || die "unknown language: '$lang'
valid (ratcheted): python java go rust typescript javascript react nextjs   (shell: excluded by design)"
  local -a targets=("$FIXTURE_DIR/$lang")
  local d
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    case "$d" in "$FIXTURE_DIR"|"$FIXTURE_DIR"/*) continue ;; esac
    targets+=("$d")
  done < <(bash "$REPO_ROOT/scripts/run-lang-tests.sh" "$lang" --list-roots 2>/dev/null | sed -n 's/^project: //p')

  local worst=0 d pct key rc
  for d in "${targets[@]}"; do
    pct="$(extract "$lang" "$d")"
    # An empty result = extraction produced nothing. That is a broken lane, not 0% — the same
    # distinction the test lanes draw between "found no tests" and "tests failed".
    [ -n "$pct" ] || { printf 'RATCHET BROKEN: no coverage figure for %s in %s\n' "$lang" "$d" >&2; exit 2; }
    key="$lang:${d#$SCAN_ROOT/}"
    compare "$key" "$pct" "$BASELINE_FILE"; rc=$?
    [ "$rc" -eq 2 ] && exit 2
    [ "$rc" -eq 1 ] && worst=1
  done
  [ "$worst" -eq 0 ] || { printf '%s: coverage regressed in at least one project.\n' "$lang" >&2; exit 1; }
  printf 'OK — %s: coverage held or improved across %d project(s).\n' "$lang" "${#targets[@]}"
}

main() {
  [ $# -ge 1 ] || die "usage: coverage-ratchet.sh <run <lang>|compare <key> <pct> <file>|--supports <lang>>"
  case "$1" in
    --supports) shift; supports "${1:-}" && exit 0 || exit 2 ;;
    compare)    shift; [ $# -eq 3 ] || die "usage: compare <key> <pct> <baseline-file>"; compare "$1" "$2" "$3" ;;
    run)        shift; [ $# -eq 1 ] || die "usage: run <lang>"; run_lang "$1" ;;
    *)          die "unknown command: '$1'" ;;
  esac
}

main "$@"
