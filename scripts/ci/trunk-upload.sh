#!/usr/bin/env bash
# trunk-upload.sh (B189) — upload every JUnit report under a root to Trunk Flaky Tests.
#
#   usage: trunk-upload.sh <junit-root>
#
# Each immediate subdirectory of <junit-root> is one test source and becomes one Trunk VARIANT
# (reports/junit/shell-tests/*.xml -> variant shell-tests), so history and flakiness stay per source.
# A subdirectory with no XML is named and skipped; the other sources still upload.
#
# THE VERDICT IS THE CLI'S PRINTED OUTPUT, NOT ITS EXIT CODE. trunk-analytics-cli 0.16.1, observed 2026-11-06:
#   - a landed upload prints "Upload: https://app.trunk.io/..." and a "Test Report" block;
#   - it then exits 1 when tests FAILED (the upload still landed — the test steps already went red for that);
#   - a refused upload prints "Error Encountered" and exits 70;
#   - one run with no CA bundle printed "unexpected error" and exited 0, and another hung for minutes.
# So an upload counts only when both lines are present, "Error Encountered" is absent, the exit is 0 or 1,
# and it finished inside TRUNK_UPLOAD_TIMEOUT. Anything else is UPLOAD FAILED (exit 1), never a silent pass.
#
# Env:
#   TRUNK_API_TOKEN       required — the LEGACY org token (the v2 API keys are not accepted by the CLI).
#                         Never printed: every line of CLI output is redacted before it is shown.
#   TRUNK_COLLECTION_ID   required — the 8-character collection id (weyland-lab: see docs/runbooks/trunk-flaky-tests.md).
#   TRUNK_ORG_SLUG        default weyland
#   TRUNK_REPO_URL        default https://github.com/edtbl76/weyland-lab (the identity Trunk files tests under)
#   TRUNK_CLI             default trunk-analytics-cli (on PATH)
#   TRUNK_UPLOAD_TIMEOUT  seconds per variant, default 300
#   CI_COMMIT_SHA / CI_COMMIT_BRANCH   Woodpecker's; a CI checkout is a detached HEAD, so the branch must be passed.
#
# EXIT: 0 every source uploaded · 1 at least one upload failed (named) · 2 could not run (no token, no
# collection, no root, no reports at all).
set -uo pipefail

die() { printf '%s\n' "$*" >&2; exit 2; }

ROOT_DIR="${1:-}"
[ -n "$ROOT_DIR" ] || die "usage: trunk-upload.sh <junit-root>"
[ -d "$ROOT_DIR" ] || die "$ROOT_DIR is not a directory"
[ -n "${TRUNK_API_TOKEN:-}" ] || die "TRUNK_API_TOKEN is not set (the Woodpecker secret trunk_org_token)"
[ -n "${TRUNK_COLLECTION_ID:-}" ] || die "TRUNK_COLLECTION_ID is not set"

SLUG="${TRUNK_ORG_SLUG:-weyland}"
REPO_URL="${TRUNK_REPO_URL:-https://github.com/edtbl76/weyland-lab}"
CLI="${TRUNK_CLI:-trunk-analytics-cli}"
TIMEOUT="${TRUNK_UPLOAD_TIMEOUT:-300}"

redact() { local s="$1"; printf '%s\n' "${s//"$TRUNK_API_TOKEN"/<redacted>}"; }

# Sources = subdirectories holding at least one .xml (at any depth: Gradle and Surefire nest theirs).
sources=()
for d in "$ROOT_DIR"/*/; do
  [ -d "$d" ] || continue
  v="$(basename "$d")"
  if [ -n "$(find "$d" -type f -name '*.xml' -print -quit)" ]; then sources+=("$v")
  else printf '%s: no JUnit files, skipped\n' "$v"; fi
done
[ "${#sources[@]}" -gt 0 ] || die "no JUnit reports under $ROOT_DIR — nothing ran, or nothing wrote a report"

extra=()
[ -n "${CI_COMMIT_SHA:-}" ] && extra+=(--repo-head-sha "$CI_COMMIT_SHA")
[ -n "${CI_COMMIT_BRANCH:-}" ] && extra+=(--repo-head-branch "$CI_COMMIT_BRANCH")

failed=0
for v in "${sources[@]}"; do
  out="$(timeout "$TIMEOUT" "$CLI" upload \
          --org-url-slug "$SLUG" \
          --test-collection-id "$TRUNK_COLLECTION_ID" \
          --junit-paths "$ROOT_DIR/$v/**/*.xml" \
          --allow-empty-test-results=false \
          --repo-url "$REPO_URL" \
          --variant "$v" \
          "${extra[@]+"${extra[@]}"}" 2>&1)"
  rc=$?
  redact "$out"
  # GNU timeout exits 124; BusyBox's (Alpine, the CI image) exits 143 — the child's SIGTERM status.
  if [ "$rc" -eq 124 ] || [ "$rc" -eq 143 ]; then
    printf 'UPLOAD FAILED: %s — timed out after %ss\n' "$v" "$TIMEOUT" >&2; failed=$((failed + 1)); continue
  fi
  if [[ "$out" == *"Error Encountered"* ]] || [[ "$out" != *"Upload: https://app.trunk.io/"* ]] \
     || [[ "$out" != *"Test Report"* ]] || { [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; }; then
    printf 'UPLOAD FAILED: %s — the CLI did not confirm the upload (exit %d)\n' "$v" "$rc" >&2
    failed=$((failed + 1)); continue
  fi
  if [ "$rc" -eq 1 ]; then printf '%s: uploaded (tests failed — reported in Trunk)\n' "$v"
  else printf '%s: uploaded\n' "$v"; fi
done

if [ "$failed" -gt 0 ]; then
  printf '%d of %d variant(s) did NOT reach Trunk\n' "$failed" "${#sources[@]}" >&2
  exit 1
fi
printf 'OK — %d variant(s) uploaded to Trunk (collection %s)\n' "${#sources[@]}" "$TRUNK_COLLECTION_ID"
exit 0
