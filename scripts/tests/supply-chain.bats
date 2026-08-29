#!/usr/bin/env bats
#
# scripts/supply-chain.sh — SBOM / sign / attest / licences / VULN, and the resilient `all` (B88 #3).
#
# Two things this suite pins that the real #41 build log proved were broken:
#   1. `vuln` — trivy's per-build vulnerability scan. LOUD BUT NON-FATAL (a base-image CVE at build
#      time is a count, not a gate), and it MUST distinguish "scanned, 0 findings" from "could not
#      scan": reading 0 off a scan that never ran is the absence-as-success trap. It reads what trivy
#      PRINTS (the report), never its exit code alone.
#   2. `all` RESILIENCE — before this, sign's hard-exit on a missing COSIGN_KEY aborted the whole
#      script, so licences and vuln NEVER ran in CI. Steps now return (never exit) and `all` collects
#      the worst outcome, so a missing key breaks sign/attest ONLY.

load helper

SC="$REPO_ROOT/scripts/supply-chain.sh"

setup() {
  setup_stubs
  export WEYLAND_SBOM_DIR="$STUB_DIR/sbom"   # keep artifacts out of /tmp
  unset COSIGN_KEY COSIGN_PUBKEY             # default: no signing key (the CI reality until A1)
}
teardown() { teardown_stubs; return 0; }

# A minimal but REAL-SHAPED trivy vuln report (fields verified against live trivy 0.74 output):
# 3 findings — 1 CRITICAL, 1 HIGH, 1 LOW.
TRIVY_FINDINGS='{"SchemaVersion":2,"ArtifactName":"img","Results":[{"Vulnerabilities":[{"VulnerabilityID":"CVE-1","Severity":"CRITICAL"},{"VulnerabilityID":"CVE-2","Severity":"HIGH"},{"VulnerabilityID":"CVE-3","Severity":"LOW"}]}]}'
TRIVY_CLEAN='{"SchemaVersion":2,"ArtifactName":"img","Results":[]}'

# ── vuln ─────────────────────────────────────────────────────────────────────
@test "vuln: findings are COUNTED and reported, but NON-FATAL (exit 0)" {
  stub trivy 0 "$TRIVY_FINDINGS"
  run bash "$SC" vuln registry.test/img:tag
  [ "$status" -eq 0 ]
  [[ "$output" == *"3 finding(s)"* ]]
  [[ "$output" == *"CRITICAL 1"* ]]
  [[ "$output" == *"HIGH 1"* ]]
}

@test "vuln: a clean image (report present, 0 findings) passes with a 0 count" {
  stub trivy 0 "$TRIVY_CLEAN"
  run bash "$SC" vuln registry.test/img:tag
  [ "$status" -eq 0 ]
  [[ "$output" == *"0 finding(s)"* ]]
}

@test "vuln: trivy exiting NON-ZERO is a BROKEN scan (2), never a pass" {
  stub trivy 1 ""
  run bash "$SC" vuln registry.test/img:tag
  [ "$status" -eq 2 ]
  [[ "$output" == *"BROKEN"* ]]
}

@test "vuln: trivy exit 0 but NO report (garbage/error text) is BROKEN (2) — the absence-as-success guard" {
  # e.g. an insecure-registry pull error that trivy still exits 0 on. Reading "0 findings" off this
  # would be verifying nothing. No SchemaVersion in the output -> it never scanned -> 2.
  stub trivy 0 "FATAL failed to pull image: tls: unknown authority"
  run bash "$SC" vuln registry.test/img:tag
  [ "$status" -eq 2 ]
}

@test "vuln: a LARGE valid report (8GB-image scale) is not falsely called broken" {
  # Regression for the pipefail+SIGPIPE trap: `printf huge | grep -q` had grep short-circuit and
  # SIGPIPE the printf, so pipefail reported the pipeline failed and the guard called a good scan
  # broken. The here-string guard is immune. Build a big report: SchemaVersion up top, thousands of
  # findings after — the exact shape that broke the real 8.48GB dagster-user-code scan in CI.
  local big='{"SchemaVersion":2,"ArtifactName":"img","Results":[{"Vulnerabilities":['
  local i
  for i in $(seq 1 2000); do big+='{"VulnerabilityID":"CVE-x","Severity":"HIGH"},'; done
  big+='{"VulnerabilityID":"CVE-z","Severity":"CRITICAL"}]}]}'
  stub trivy 0 "$big"
  run bash "$SC" vuln registry.test/img:tag
  [ "$status" -eq 0 ]
  [[ "$output" == *"2001 finding(s)"* ]]
  [[ "$output" == *"CRITICAL 1"* ]]
}

@test "vuln: trivy not on PATH is a BROKEN lane (2)" {
  run bash "$SC" vuln registry.test/img:tag
  [ "$status" -eq 2 ]
  [[ "$output" == *"trivy"* ]]
}

# ── all — resilience (the load-bearing fix) ──────────────────────────────────
@test "all: a missing COSIGN_KEY breaks sign/attest but licences and VULN still run (resilient)" {
  # THE regression this closes: before the refactor, sign's die-exit aborted the whole script here,
  # so licences and vuln never executed. Now they must — and the vuln OK line proves it.
  stub syft 0 ""
  stub cosign 0 ""
  stub trivy 0 "$TRIVY_FINDINGS"
  # COSIGN_KEY intentionally unset (setup unsets it).
  run bash "$SC" all registry.test/img:tag
  [ "$status" -eq 2 ]                                # worst outcome = sign/attest broken
  [[ "$output" == *"vuln scan"* ]]                  # vuln RAN despite the broken sign
  [[ "$output" == *"COSIGN_KEY is unset"* ]]        # and the broken step still reported why
}

@test "all: with everything available, the whole chain runs clean (exit 0)" {
  export COSIGN_KEY="$STUB_DIR/fake.key"            # non-empty -> sign/attest proceed to (stubbed) cosign
  stub syft 0 ""
  stub cosign 0 ""
  stub trivy 0 "$TRIVY_CLEAN"
  run bash "$SC" all registry.test/img:tag
  [ "$status" -eq 0 ]
  [[ "$output" == *"vuln scan"* ]]
  [[ "$output" == *"SBOM written"* ]]
}

# ── sbom / step contracts ────────────────────────────────────────────────────
@test "sbom: a syft that cannot produce an SBOM is BROKEN (2), not a finding (1)" {
  stub syft 1 "error: cannot parse image"
  run bash "$SC" sbom registry.test/img:tag
  [ "$status" -eq 2 ]
  [[ "$output" == *"SBOM BROKEN"* ]]
}

@test "a single subcommand PROPAGATES its exit code (sign, no cosign -> 2)" {
  # no cosign stub -> has cosign fails -> broken (2), and main exits with it.
  run bash "$SC" sign registry.test/img:tag
  [ "$status" -eq 2 ]
  [[ "$output" == *"cosign"* ]]
}

# ── vuln DELTA vs the deployed image (gap #3 completion) ─────────────────────
# These need trivy to return DIFFERENT reports for the new vs the deployed image, so a per-image stub.
# Multi-line JSON (one finding per line) so the awk ID/Severity pairing behaves like real trivy output.
setup_trivy_keyed() {
  TRIVY_DIR="$STUB_DIR/trivy_resp"; mkdir -p "$TRIVY_DIR"; export TRIVY_DIR
  cat >"$STUB_DIR/trivy" <<'TRIVY'
#!/usr/bin/env bash
ref="${!#}"                                   # the image ref is the last positional arg
key="$(printf '%s' "$ref" | tr '/:.' '___')"
spec="$TRIVY_DIR/$key"
[ -f "$spec" ] || { echo "no trivy stub for $ref" >&2; exit 3; }
rc="$(sed -n 1p "$spec")"; sed -n '2,$p' "$spec"
exit "$rc"
TRIVY
  chmod +x "$STUB_DIR/trivy"
}
trivy_resp() {
  local k; k="$(printf '%s' "$1" | tr '/:.' '___')"
  { printf '%s\n' "$2"; printf '%s' "$3"; } >"$TRIVY_DIR/$k"
}
J_OLD='{"SchemaVersion":2,"ArtifactName":"img","Results":[{"Vulnerabilities":[
{"VulnerabilityID":"CVE-1","Severity":"LOW"},
{"VulnerabilityID":"CVE-2","Severity":"HIGH"}
]}]}'
J_NEW_ADDS_CRIT='{"SchemaVersion":2,"ArtifactName":"img","Results":[{"Vulnerabilities":[
{"VulnerabilityID":"CVE-1","Severity":"LOW"},
{"VulnerabilityID":"CVE-2","Severity":"HIGH"},
{"VulnerabilityID":"CVE-3","Severity":"CRITICAL"}
]}]}'

@test "vuln delta: a CVE in the new image but NOT the deployed one is flagged as introduced (loud)" {
  setup_trivy_keyed
  trivy_resp registry.test/img:new 0 "$J_NEW_ADDS_CRIT"
  trivy_resp registry.test/img:old 0 "$J_OLD"
  run bash "$SC" vuln registry.test/img:new registry.test/img:old
  [ "$status" -eq 0 ]
  [[ "$output" == *"+1 NEW CVE"* ]]
  [[ "$output" == *"1 CRITICAL"* ]]
  [[ "$output" == *"VULN DELTA"* ]]        # the loud stderr warning
  [[ "$output" == *"CVE-3 CRITICAL"* ]]    # names the introduced CVE
}

@test "vuln delta: new is a subset of deployed -> no new CVEs introduced" {
  setup_trivy_keyed
  trivy_resp registry.test/img:new 0 "$J_OLD"
  trivy_resp registry.test/img:old 0 "$J_OLD"
  run bash "$SC" vuln registry.test/img:new registry.test/img:old
  [ "$status" -eq 0 ]
  [[ "$output" == *"no new CVEs introduced"* ]]
  [[ "$output" != *"VULN DELTA"* ]]
}

@test "vuln delta: an unscannable baseline degrades to absolute count, NOT broken" {
  # the new image scans fine; the deployed one cannot be pulled -> report the count, skip the delta.
  setup_trivy_keyed
  trivy_resp registry.test/img:new 0 "$J_NEW_ADDS_CRIT"
  trivy_resp registry.test/img:old 1 ""
  run bash "$SC" vuln registry.test/img:new registry.test/img:old
  [ "$status" -eq 0 ]
  [[ "$output" == *"absolute count only"* ]]
}

@test "an unknown subcommand exits 2 with the valid list" {
  run bash "$SC" frobnicate registry.test/img:tag
  [ "$status" -eq 2 ]
  [[ "$output" == *"vuln"* ]]
}
