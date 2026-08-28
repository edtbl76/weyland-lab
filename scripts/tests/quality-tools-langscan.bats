#!/usr/bin/env bats
#
# check-quality-tools.sh — drift guard for the quality registry (B88 Phase 2 extension).
#
# The guard already asserts that every `runner: scan-suite` tool is actually posted by scan.py. B88
# added a SECOND runner, `lang-scan`, for the toolchain-heavy scanners (Rust, Java, Node) that
# cannot live in the single scan-suite image without tripling it — oversized layers have already
# broken builds here (`unpigz: invalid deflate`).
#
# Declaring 13 tools under a runner NOTHING enforces would be the registry's own failure mode: the
# "9 vs 10" drift it was built to stop, reintroduced through a new door. These cases assert the
# guard covers lang-scan the same way it covers scan-suite.

load helper

setup() {
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-quality-tools.sh"
}

teardown() { teardown_stubs; return 0; }

@test "the guard passes against the real repo as shipped" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "the guard reports on BOTH runners, not just scan-suite" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan-suite"* ]]
  [[ "$output" == *"lang-scan"* ]]
}

@test "a lang-scan tool declared in the registry but NOT wired is caught" {
  # The whole point: registry and implementation must not drift. A tool that exists only as a
  # registry line is documentation, not coverage — and this repo already has a Phase 3 finding that
  # says exactly that about syft/cosign/SLSA.
  reg="$(mktemp)"; scan="$(mktemp)"; lang="$(mktemp)"
  cat > "$reg" <<'YAML'
tools:
  - {id: clippy, runner: lang-scan, enabled: true}
  - {id: ghost-tool, runner: lang-scan, enabled: true}
YAML
  : > "$scan"   # no post() calls: these fixtures declare no scan-suite tools
  printf 'run_tool clippy\n' > "$lang"
  run env WEYLAND_QT_REGISTRY="$reg" WEYLAND_QT_SCAN="$scan" WEYLAND_QT_LANGSCAN="$lang" \
      bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ghost-tool"* ]]
}

@test "a tool wired in the lane script but NOT declared is caught" {
  reg="$(mktemp)"; scan="$(mktemp)"; lang="$(mktemp)"
  cat > "$reg" <<'YAML'
tools:
  - {id: clippy, runner: lang-scan, enabled: true}
YAML
  : > "$scan"   # no post() calls: these fixtures declare no scan-suite tools
  printf 'run_tool clippy\nrun_tool undeclared-tool\n' > "$lang"
  run env WEYLAND_QT_REGISTRY="$reg" WEYLAND_QT_SCAN="$scan" WEYLAND_QT_LANGSCAN="$lang" \
      bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"undeclared-tool"* ]]
}

@test "a DISABLED lang-scan tool is not required to be wired" {
  reg="$(mktemp)"; scan="$(mktemp)"; lang="$(mktemp)"
  cat > "$reg" <<'YAML'
tools:
  - {id: clippy, runner: lang-scan, enabled: true}
  - {id: parked-tool, runner: lang-scan, enabled: false}
YAML
  : > "$scan"   # no post() calls: these fixtures declare no scan-suite tools
  printf 'run_tool clippy\n' > "$lang"
  run env WEYLAND_QT_REGISTRY="$reg" WEYLAND_QT_SCAN="$scan" WEYLAND_QT_LANGSCAN="$lang" \
      bash "$GUARD"
  [ "$status" -eq 0 ]
}
