#!/bin/sh
# apt-install.sh — install Debian/Ubuntu packages in a CI step, retrying transient upstream failures (2026-11-10).
#
#   usage: sh scripts/ci/apt-install.sh [apt-get install flags] <package>...
#   e.g.   sh scripts/ci/apt-install.sh --no-install-recommends build-essential git curl
#
# Every attempt runs `apt-get update` and then `apt-get install -y <args>`. Re-running update is the point: nightly
# #622 failed because Ubuntu's security pocket replaced a package (perl-base) while a slow install was still
# downloading, so the index pointed at a .deb that no longer existed (404). A fresh index fixes that; so does a retry
# after a mirror's brief 5xx. Up to 3 attempts, APT_RETRY_DELAY seconds apart (default 15), then exit with apt-get's
# status and a line naming the packages. POSIX sh: the CI images do not all have bash. Tests:
# scripts/tests/apt-install.bats, which also checks that every `apt-get install` in .woodpecker.yml uses this.
set -u

[ "$#" -gt 0 ] || { echo "usage: sh scripts/ci/apt-install.sh [apt-get install flags] <package>..." >&2; exit 2; }

ATTEMPTS=3
DELAY="${APT_RETRY_DELAY:-15}"
i=1
while :; do
  # Capture the status explicitly: after an `if` with no `else`, $? is 0, which would turn the last failure into success.
  rc=0
  apt-get update && apt-get install -y "$@" || rc=$?
  [ "$rc" -eq 0 ] && exit 0
  if [ "$i" -ge "$ATTEMPTS" ]; then
    echo "apt-install FAILED after $ATTEMPTS attempts: $* (last exit $rc)" >&2
    exit "$rc"
  fi
  echo "apt-install: attempt $i/$ATTEMPTS failed (exit $rc); refreshing the index and retrying in ${DELAY}s" >&2
  i=$((i + 1))
  sleep "$DELAY"
done
