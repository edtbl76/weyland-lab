#!/usr/bin/env bats
#
# scripts/coverage-ratchet.sh — per-language coverage RATCHET (B88 gap #1).
#
# WHY A RATCHET, NOT AN 80% FLOOR. `org.md` names an 80% line-coverage floor, but a hard threshold
# on lanes that are mostly hello-world fixtures (Rust has no production code, Java is 2 modules)
# either fails on day one or forces fake tests to pad the number — and coverage % is the metric that
# most invites gaming (80% testing getters). A threshold that fires on honest low coverage gets
# muted, the same failure this repo keeps naming about permanently-lit alerts. The ratchet fails ONLY
# when coverage DROPS against a committed baseline: new untested code is caught, existing gaps are
# not a false alarm, and a number that only has to not-decrease cannot be gamed upward.
#
# WHY THIS EXISTS AT ALL. Exactly one lane (Go) writes a coverage profile today and NOTHING reads it
# — a number produced and discarded, which is the absence-as-success pattern in its purest form.
#
# EXIT CODES mirror the test lanes:
#   0  coverage held or improved (baseline recorded/updated)
#   1  coverage REGRESSED against the baseline  -> a real finding
#   2  the ratchet could not run                -> broken lane (missing tool, unparseable number)

load helper

setup() {
  setup_stubs
  R="$REPO_ROOT/scripts/coverage-ratchet.sh"
  SANDBOX="$(mktemp -d)"
  BASELINE="$SANDBOX/baseline.tsv"
  export SANDBOX BASELINE
}

teardown() {
  teardown_stubs
  [ -n "${SANDBOX:-}" ] && [ -d "$SANDBOX" ] && rm -rf "$SANDBOX"
  return 0
}

# The ratchet's pure comparison is exposed as `compare <key> <pct> <baseline-file>` so it is testable
# without any real toolchain. The per-language extraction is integration-tested separately.

@test "a brand-new project RECORDS its baseline and passes (nothing to regress against)" {
  run bash "$R" compare go:/svc/a 42.0 "$BASELINE"
  [ "$status" -eq 0 ]
  [[ "$output" == *"baseline"* || "$output" == *"recorded"* ]]
  grep -q "go:/svc/a	42.0" "$BASELINE"
}

@test "coverage HOLDING at the baseline passes" {
  printf 'go:/svc/a\t42.0\n' > "$BASELINE"
  run bash "$R" compare go:/svc/a 42.0 "$BASELINE"
  [ "$status" -eq 0 ]
}

@test "coverage IMPROVING passes AND ratchets the baseline up" {
  printf 'go:/svc/a\t42.0\n' > "$BASELINE"
  run bash "$R" compare go:/svc/a 57.3 "$BASELINE"
  [ "$status" -eq 0 ]
  grep -q "go:/svc/a	57.3" "$BASELINE"
  ! grep -q "42.0" "$BASELINE"
}

@test "coverage DROPPING fails with exit 1 and names both numbers" {
  printf 'go:/svc/a\t80.0\n' > "$BASELINE"
  run bash "$R" compare go:/svc/a 71.5 "$BASELINE"
  [ "$status" -eq 1 ]
  [[ "$output" == *"80"* ]]
  [[ "$output" == *"71.5"* ]]
  # A regression must NOT quietly rewrite the baseline downward — that would launder the drop away.
  grep -q "go:/svc/a	80.0" "$BASELINE"
}

@test "a sub-tolerance wobble does NOT fail (float noise is not a regression)" {
  # go tool cover and pytest-cov round differently run to run; a 0.05 flicker must not page.
  printf 'go:/svc/a\t80.00\n' > "$BASELINE"
  run bash "$R" compare go:/svc/a 79.98 "$BASELINE"
  [ "$status" -eq 0 ]
}

@test "a drop BEYOND tolerance does fail" {
  printf 'go:/svc/a\t80.00\n' > "$BASELINE"
  run bash "$R" compare go:/svc/a 79.0 "$BASELINE"
  [ "$status" -eq 1 ]
}

@test "an unparseable coverage number is a BROKEN ratchet (2), never a silent pass" {
  # If extraction returns garbage, treating it as 0 would fail every project, and treating it as
  # "skip" would pass everything. Both are wrong: the ratchet could not do its job -> exit 2.
  run bash "$R" compare go:/svc/a "N/A" "$BASELINE"
  [ "$status" -eq 2 ]
  [[ "$output" == *"parse"* || "$output" == *"number"* ]]
}

@test "each project ratchets independently — one dropping doesn't hide another holding" {
  printf 'go:/svc/a\t80.0\ngo:/svc/b\t50.0\n' > "$BASELINE"
  run bash "$R" compare go:/svc/b 50.0 "$BASELINE"
  [ "$status" -eq 0 ]
  # /svc/a's line is untouched by a /svc/b comparison.
  grep -q "go:/svc/a	80.0" "$BASELINE"
}

# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------

@test "an unknown language is refused" {
  run bash "$R" run cobol
  [ "$status" -eq 2 ]
  [[ "$output" == *"cobol"* ]]
}

@test "every RATCHETED language has a coverage extractor (shell is deliberately excluded)" {
  for lang in python java go rust typescript javascript react nextjs; do
    run bash "$R" --supports "$lang"
    [ "$status" -eq 0 ] || { echo "no coverage extractor for $lang"; return 1; }
  done
}

@test "shell coverage is EXCLUDED, and the skip is reported loudly, not silent" {
  # A silent skip would be the exact absence-as-success this ratchet exists to prevent. `run shell`
  # must exit 0 AND say why, and --supports shell must be false so nothing treats it as covered.
  run bash "$R" --supports shell
  [ "$status" -ne 0 ]
  run bash "$R" run shell
  [ "$status" -eq 0 ]
  [[ "$output" == *"NOT ratcheted"* || "$output" == *"deliberate"* ]]
}
