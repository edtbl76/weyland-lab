#!/usr/bin/env bash
# junit.sh — JUnit report helpers shared by the test runners (sourced, not run).
# Sourced by scripts/run-lang-tests.sh (the lang lanes) and scripts/ci/golden-integration.sh (the integration tier,
# B262), so both upload reports Trunk can count.

# wrap_bare_cases <file> — node's junit reporter puts <testcase> straight under <testsuites> when tests are not in a
# describe(), and Trunk counts such cases as nothing (pipeline #592: fastify's 4 tests uploaded as 0; a dry-run
# counted 0 raw, 4 wrapped). Wrap them in one <testsuite> named after the report. A file that already has a
# <testsuite> is left alone.
wrap_bare_cases() {
  local f="$1" name
  [ -f "$f" ] && ! grep -q '<testsuite[ >]' "$f" && grep -q '<testcase' "$f" || return 0
  name="$(basename "$f" .xml)"
  awk -v n="$name" '
    /<testsuites[ >]/ && !opened { print; print "<testsuite name=\"" n "\">"; opened = 1; next }
    /<\/testsuites>/              { print "</testsuite>" }
    { print }
  ' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
}
