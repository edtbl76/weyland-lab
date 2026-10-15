#!/usr/bin/env bats
# B206 slice 2 (2026-10-15) — weyland-guard and weyland-tool-server share the guard wire contract through ONE package,
# grkit (github.com/edtbl76/grkit), instead of two byte-identical copies of guardrails/verdict.py held together by
# check-verdict-sync.sh. The drift risk moved: two copies can't diverge any more, but two PINS can. A guard built on
# v0.2.0 and a tool-server on a later grkit could disagree on the wire (Hook values are URL paths; Verdict is built
# positionally). So every grkit reference in the repo (both Dockerfiles, both test requirement files) must be one
# identical, commit-pinned URL, and both services must carry it.

setup() {
  ROOT="$BATS_TEST_DIRNAME/../.."
  S="$ROOT/nodes/mother/lab/weyland-platform/services"
}

# Print every `grkit @ <url>` reference under the services tree, one `<file>\t<url>` per line.
# find + grep, not `grep --include`: the CI bats image runs BusyBox grep, which ignores --include.
pins() {
  local out
  out="$(find "$S" \( -name Dockerfile -o -name 'requirements*.txt' \) -type f -exec grep -HoE "grkit @ [^' ]+" {} + \
    | sed -E 's/:grkit @ /\t/')"
  [ -n "$out" ] || return 3
  printf '%s\n' "$out"
}

@test "every grkit pin in the repo is the same commit-pinned archive URL" {
  run pins
  [ "$status" -eq 0 ] || { echo "no grkit pin found at all: the scan is not reading the services ($status)"; return 1; }
  n_files=$(printf '%s\n' "$output" | cut -f1 | sort -u | wc -l)
  urls=$(printf '%s\n' "$output" | cut -f2 | sort -u)
  [ "$(printf '%s\n' "$urls" | wc -l)" -eq 1 ] || { printf 'grkit pins differ:\n%s\n' "$output"; return 1; }
  # A 40-hex commit, never a branch or a moving tag.
  [[ "$urls" =~ ^https://github\.com/edtbl76/grkit/archive/[0-9a-f]{40}\.tar\.gz#subdirectory=python$ ]] \
    || { echo "not a commit-pinned archive URL: $urls"; return 1; }
  [ "$n_files" -ge 4 ] || { printf 'expected both Dockerfiles and both test requirement files, got:\n%s\n' "$output"; return 1; }
}

@test "both services pin grkit in their image AND their test lane" {
  for svc in weyland-guard weyland-tool-server; do
    grep -q "grkit @ " "$S/$svc/Dockerfile" || { echo "$svc/Dockerfile has no grkit pin"; return 1; }
    grep -q "grkit @ " "$S/$svc/requirements-test.txt" || { echo "$svc/requirements-test.txt has no grkit pin"; return 1; }
  done
}

@test "a pin that drifts in one file is caught (the check is not a rubber stamp)" {
  T="$(mktemp -d)"; mkdir -p "$T/a" "$T/b"
  printf "RUN pip install 'grkit @ https://github.com/edtbl76/grkit/archive/%040d.tar.gz#subdirectory=python'\n" 1 >"$T/a/Dockerfile"
  printf 'grkit @ https://github.com/edtbl76/grkit/archive/%040d.tar.gz#subdirectory=python\n' 2 >"$T/b/requirements-test.txt"
  S="$T" run pins
  rm -rf "$T"
  [ "$status" -eq 0 ]
  [ "$(printf '%s\n' "$output" | cut -f2 | sort -u | wc -l)" -eq 2 ]
}

@test "no service carries its own guardrails/verdict.py again" {
  [ ! -e "$S/weyland-guard/guardrails/verdict.py" ]
  [ ! -e "$S/weyland-tool-server/guardrails/verdict.py" ]
}
