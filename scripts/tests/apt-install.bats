#!/usr/bin/env bats
# scripts/ci/apt-install.sh — the bounded apt retry every CI step installs through (2026-11-10).
#
# Nightly #622's test-ada failed on `404 Not Found` for perl-base: `apt-get update` had run, but the install took ~3 min
# on a slow mirror, and Ubuntu's security pocket published a newer perl in between, so the index pointed at a .deb that
# no longer existed. One night earlier (#611) the same lane failed on a GitHub 504. A transient upstream hiccup is not a
# finding about our code, so each attempt re-runs `apt-get update` (a fresh index after a pocket swap) and retries, up to
# 3 times, then FAILS CLOSED naming the reason. These tests stub apt-get on PATH.

setup() {
  REPO="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
  SCRIPT="$REPO/scripts/ci/apt-install.sh"
  STUB="$(mktemp -d)"
  export CALLS="$STUB/calls" FAIL_INSTALLS="${FAIL_INSTALLS:-0}" APT_RETRY_DELAY=0
  cat > "$STUB/apt-get" <<'SH'
#!/bin/sh
echo "$*" >> "$CALLS"
if [ "$1" = install ]; then
  n=$(grep -c '^install' "$CALLS")
  [ "$n" -le "$FAIL_INSTALLS" ] && { echo "E: Failed to fetch ... 404  Not Found" >&2; exit 100; }
fi
exit 0
SH
  chmod +x "$STUB/apt-get"
  export PATH="$STUB:$PATH"
}

teardown() { rm -rf "$STUB"; }

@test "installs on the first attempt: one update, one install, the packages and flags passed through" {
  run sh "$SCRIPT" --no-install-recommends curl unzip
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(grep -c '^update' "$CALLS")" -eq 1 ]
  grep -qx 'install -y --no-install-recommends curl unzip' "$CALLS"
}

@test "a failed install is retried after a fresh update, and succeeds on the second attempt" {
  FAIL_INSTALLS=1 run sh "$SCRIPT" curl
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(grep -c '^update' "$CALLS")" -eq 2 ]
  [ "$(grep -c '^install' "$CALLS")" -eq 2 ]
  [[ "$output" == *"attempt 1/3 failed"* ]]
}

@test "three failed attempts fail closed, naming the packages and the attempt count" {
  FAIL_INSTALLS=9 run sh "$SCRIPT" cppcheck
  [ "$status" -ne 0 ]
  [[ "$output" == *"apt-install FAILED after 3 attempts: cppcheck"* ]]
  [ "$(grep -c '^install' "$CALLS")" -eq 3 ]
}

@test "no packages is a usage error, not a silent success" {
  run sh "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
}

@test "every apt-get install in .woodpecker.yml goes through the retry helper" {
  run grep -n 'apt-get install' "$REPO/.woodpecker.yml"
  [ "$status" -eq 1 ] || { echo "steps that call apt-get install directly (use scripts/ci/apt-install.sh):"; echo "$output"; return 1; }
  [ "$(grep -c 'scripts/ci/apt-install.sh' "$REPO/.woodpecker.yml")" -ge 9 ]
}
