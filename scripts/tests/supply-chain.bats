#!/usr/bin/env bats
#
# scripts/supply-chain.sh — SBOM, signing, provenance, licences (B88 Phase 3).
#
# THE FINDING THIS EXISTS TO CLOSE. Every supply-chain concept in this lab was present as KNOWLEDGE
# and absent as IMPLEMENTATION: syft, cosign, sigstore, SBOM, CycloneDX, SPDX, SLSA, provenance,
# attestation and Renovate appeared ONLY under knowledge-repos/. The estate documented a supply
# chain it did not have.
#
# WHY THE ORDER OF OPERATIONS IS SAFETY-CRITICAL. Signing is additive — an unsigned image keeps
# working. VERIFICATION is not: a Gatekeeper policy that requires signatures would reject every
# image already running and take the cluster down. So the policy ships in `enforcementAction:
# dryrun`, matching the convention already written into k8s/gatekeeper/constraints.yaml ("ALL start
# in dryrun — violations are audited but NOTHING is blocked"). These tests assert that default.
#
# ASSERT THE REASON, NOT JUST THE STATUS — exit 127 satisfies `-ne 0`.

load helper

setup() {
  setup_stubs
  SC="$REPO_ROOT/scripts/supply-chain.sh"
  SANDBOX="$(mktemp -d)"
  export SANDBOX
}

teardown() {
  teardown_stubs
  [ -n "${SANDBOX:-}" ] && [ -d "$SANDBOX" ] && rm -rf "$SANDBOX"
  return 0
}

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

@test "an unknown subcommand is refused and the valid set is named" {
  run bash "$SC" teleport
  [ "$status" -eq 2 ]
  [[ "$output" == *"teleport"* ]]
  [[ "$output" == *"sbom"* ]]
  [[ "$output" == *"sign"* ]]
}

@test "no subcommand prints usage rather than doing something" {
  run bash "$SC"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
}

# ---------------------------------------------------------------------------
# Fail closed on a missing tool — never skip
# ---------------------------------------------------------------------------

@test "sbom fails closed when syft is absent, and names it" {
  run env PATH="$STUB_DIR:/usr/bin:/bin" bash "$SC" sbom registry.weyland.lab/x:git-abc
  [ "$status" -eq 2 ]
  [[ "$output" == *"syft"* ]]
  [[ "$output" != *"OK — "* ]]   # NB: "OK" alone matches "BROKEN" (B-R-O-K-E-N)
}

@test "sign fails closed when cosign is absent, and names it" {
  run env PATH="$STUB_DIR:/usr/bin:/bin" bash "$SC" sign registry.weyland.lab/x:git-abc
  [ "$status" -eq 2 ]
  [[ "$output" == *"cosign"* ]]
}

@test "sign refuses to run without a signing key rather than silently not signing" {
  # An unsigned image that reports success is the whole failure mode: verification later says
  # "no signature" and nobody knows whether signing ran or was skipped.
  stub cosign 0 "signed"
  run env COSIGN_KEY= bash "$SC" sign registry.weyland.lab/x:git-abc
  [ "$status" -eq 2 ]
  [[ "$output" == *"key"* ]]
}

# ---------------------------------------------------------------------------
# The happy paths actually invoke the tools
# ---------------------------------------------------------------------------

@test "sbom emits BOTH CycloneDX and SPDX, not just one" {
  # Two formats because they answer to different consumers: CycloneDX for vuln tooling, SPDX for
  # licence/compliance. Emitting one and claiming an SBOM would be half the artifact.
  stub syft 0 "sbom written"
  run env WEYLAND_SBOM_DIR="$SANDBOX" bash "$SC" sbom registry.weyland.lab/x:git-abc
  [ "$status" -eq 0 ]
  grep -q "cyclonedx" "$STUB_LOG"
  grep -q "spdx" "$STUB_LOG"
}

@test "sign passes the image reference through to cosign" {
  stub cosign 0 "signed"
  run env COSIGN_KEY=/tmp/k.key bash "$SC" sign registry.weyland.lab/x:git-abc
  [ "$status" -eq 0 ]
  grep -q "registry.weyland.lab/x:git-abc" "$STUB_LOG"
}

@test "attest records SLSA provenance, not a bare signature" {
  stub cosign 0 "attested"
  run env COSIGN_KEY=/tmp/k.key WEYLAND_SBOM_DIR="$SANDBOX" \
      bash "$SC" attest registry.weyland.lab/x:git-abc
  [ "$status" -eq 0 ]
  grep -qi "attest" "$STUB_LOG"
  grep -qi "slsaprovenance\|provenance" "$STUB_LOG"
}

@test "licences are scanned with trivy's licence scanner specifically" {
  stub trivy 0 "no license findings"
  run bash "$SC" licenses registry.weyland.lab/x:git-abc
  [ "$status" -eq 0 ]
  grep -q -- "--scanners" "$STUB_LOG"
  grep -q "license" "$STUB_LOG"
}

# ---------------------------------------------------------------------------
# A tool that fails must not be reported as success
# ---------------------------------------------------------------------------

@test "a failing syft is a failure, not a shrug" {
  # `-ne 0` ALONE IS NOT ENOUGH — exit 127 (command not found) satisfies it, and the first version
  # of this test passed in the Red run against a script that did not exist. Fourth occurrence of
  # this trap in the repo. Assert the script's OWN diagnostic, which a missing file cannot emit.
  stub syft 1 "syft exploded"
  run env WEYLAND_SBOM_DIR="$SANDBOX" bash "$SC" sbom registry.weyland.lab/x:git-abc
  [ "$status" -eq 1 ]
  [[ "$output" == *"SBOM"* || "$output" == *"sbom"* ]]
  [[ "$output" != *"OK — "* ]]   # NB: "OK" alone matches "BROKEN" (B-R-O-K-E-N)
}

@test "a failing cosign sign is a failure" {
  stub cosign 1 "signing failed"
  run env COSIGN_KEY=/tmp/k.key bash "$SC" sign registry.weyland.lab/x:git-abc
  [ "$status" -eq 1 ]
  [[ "$output" == *"sign"* ]]
  [[ "$output" != *"OK — "* ]]   # NB: "OK" alone matches "BROKEN" (B-R-O-K-E-N)
}

# ---------------------------------------------------------------------------
# verify — and the safety property that matters most
# ---------------------------------------------------------------------------

@test "verify reports an UNSIGNED image as unverified, never as fine" {
  stub cosign 1 "no matching signatures"
  run env COSIGN_PUBKEY=/tmp/k.pub bash "$SC" verify registry.weyland.lab/x:git-abc
  [ "$status" -ne 0 ]
  [[ "$output" == *"nsigned"* || "$output" == *"not verified"* || "$output" == *"no matching"* ]]
}

@test "the Gatekeeper signature policy ships in dryrun, NOT deny" {
  # THE most important assertion in this file. Requiring signatures on a cluster whose images are
  # all unsigned would reject every workload. k8s/gatekeeper/constraints.yaml already states the
  # house rule — ALL constraints start in dryrun — and this keeps the new one honest.
  policy="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/gatekeeper/image-signatures.yaml"
  [ -f "$policy" ]
  run grep -c "enforcementAction: dryrun" "$policy"
  [ "$status" -eq 0 ]
  [ "$output" -ge 1 ]
  # And no ACTIVE line may set deny. The file documents how to promote it, so a naive grep matches
  # the instructions — strip comments before asserting.
  run bash -c "grep -v '^[[:space:]]*#' '$policy' | grep -c 'enforcementAction: deny' || true"
  [ "$output" -eq 0 ]
}

@test "the signature policy documents how to promote it to deny" {
  # A dryrun policy nobody knows how to graduate stays dryrun forever, which is its own kind of
  # theatre. The file must say what to check and what to flip.
  policy="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/gatekeeper/image-signatures.yaml"
  run grep -ci "totalViolations\|promote\|flip" "$policy"
  [ "$output" -ge 1 ]
}
