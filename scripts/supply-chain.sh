#!/usr/bin/env bash
#
# supply-chain.sh — SBOM, signing, provenance and licences for the images this lab ships (B88 Ph3).
#
# THE FINDING THIS CLOSES. Every supply-chain concept in this lab existed as KNOWLEDGE and nowhere
# as IMPLEMENTATION: `syft`, `cosign`, `sigstore`, SBOM, CycloneDX, SPDX, SLSA, provenance,
# attestation and Renovate appeared ONLY under `knowledge-repos/`. The estate documented a supply
# chain it did not have. The leverage was always there — `scripts/ci/images.tsv` and the ship loop
# already know every image and tag — so this is a handful of steps, not a platform.
#
# SUBCOMMANDS
#   sbom <image>      syft -> CycloneDX **and** SPDX. Two formats because they serve different
#                     consumers: CycloneDX feeds vulnerability tooling, SPDX feeds licence and
#                     compliance. Emitting one and calling it "an SBOM" is half an artifact.
#   sign <image>      cosign sign with a key pair. NOT keyless: keyless needs Fulcio/OIDC over the
#                     internet and this is a LAN-only lab, so the private key lives in a
#                     SealedSecret and the public key ships with the Gatekeeper policy.
#   attest <image>    cosign attest, SLSA provenance predicate — WHO built it, from WHAT source, on
#                     WHICH commit. A signature says "we vouch for this blob"; provenance says where
#                     the blob came from, and only the second survives the question "rebuilt from
#                     what?".
#   verify <image>    cosign verify against the public key. The read-only half.
#   licenses <image>  trivy's licence scanner specifically (`--scanners license`), which is a
#                     different question from its vulnerability scan and is not run by the suite.
#   all <image>       sbom -> sign -> attest -> licenses, in that order.
#
# EXIT CODES
#   0  the step ran and reported clean
#   1  the step ran and FOUND something (a failed signature, a licence violation)
#   2  the step COULD NOT RUN — missing tool, missing key, bad arguments
# 1 and 2 are not interchangeable: "we looked and it is unsigned" and "we never looked" are
# different facts, and this repo has repeatedly shipped the second while reporting the first.
#
# NOTHING HERE ENFORCES. Signing an image cannot break a running cluster; REQUIRING a signature can.
# Admission control lives in k8s/gatekeeper/image-signatures.yaml and ships in `dryrun`.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SBOM_DIR="${WEYLAND_SBOM_DIR:-${TMPDIR:-/tmp}/weyland-sbom}"

die() { printf '%s\n' "$*" >&2; exit 2; }

usage() {
  cat >&2 <<'EOF'
usage: supply-chain.sh <sbom|sign|attest|verify|licenses|all> <image-ref>

  sbom      syft -> CycloneDX + SPDX
  sign      cosign sign            (needs COSIGN_KEY)
  attest    cosign attest, SLSA provenance predicate (needs COSIGN_KEY)
  verify    cosign verify          (needs COSIGN_PUBKEY)
  licenses  trivy --scanners license
  all       sbom -> sign -> attest -> licenses

exit 0 clean · 1 found something · 2 could not run
EOF
  exit 2
}

need() {
  command -v "$1" >/dev/null 2>&1 || \
    die "LANE BROKEN: \`$1\` is not on PATH. Refusing to report success for a step that never ran."
}

# ── SBOM ─────────────────────────────────────────────────────────────────────
sbom() {
  local img="$1" safe out rc=0
  need syft
  safe="$(printf '%s' "$img" | tr '/:' '__')"
  mkdir -p "$SBOM_DIR"
  for fmt in cyclonedx-json spdx-json; do
    out="$SBOM_DIR/${safe}.${fmt%%-*}.json"
    if ! syft "$img" -o "$fmt=$out" >/dev/null 2>&1; then
      printf 'SBOM FAILED: syft could not produce %s for %s\n' "$fmt" "$img" >&2
      rc=1
    fi
  done
  [ "$rc" -eq 0 ] || return 1
  printf 'OK — SBOM written for %s (cyclonedx + spdx) in %s\n' "$img" "$SBOM_DIR"
}

# ── signing ──────────────────────────────────────────────────────────────────
sign() {
  local img="$1"
  need cosign
  # A missing key must NOT degrade to "did not sign, carried on". An unsigned image that reported
  # success is indistinguishable later from one whose signature was stripped.
  [ -n "${COSIGN_KEY:-}" ] || \
    die "LANE BROKEN: COSIGN_KEY is unset — refusing to 'sign' without a key.
The private key comes from the SealedSecret cosign-signing-key; see runbooks/supply-chain.md."
  if ! cosign sign --key "$COSIGN_KEY" --yes "$img" >/dev/null 2>&1; then
    printf 'SIGN FAILED: cosign could not sign %s\n' "$img" >&2
    return 1
  fi
  printf 'OK — signed %s\n' "$img"
}

# ── provenance ───────────────────────────────────────────────────────────────
attest() {
  local img="$1" pred
  need cosign
  [ -n "${COSIGN_KEY:-}" ] || die "LANE BROKEN: COSIGN_KEY is unset — cannot attest."
  mkdir -p "$SBOM_DIR"
  pred="$SBOM_DIR/provenance.json"
  # A minimal in-toto SLSA provenance predicate. The values come from CI, and every one of them is
  # a question you cannot answer from the image alone: which commit, which pipeline, which builder.
  cat > "$pred" <<EOF
{
  "buildType": "https://weyland.lab/buildtypes/woodpecker/v1",
  "builder": { "id": "https://ci.weyland.lab/woodpecker" },
  "invocation": {
    "configSource": {
      "uri": "git+https://github.com/edtbl76/weyland-lab",
      "digest": { "sha1": "${CI_COMMIT_SHA:-unknown}" },
      "entryPoint": ".woodpecker.yml"
    }
  },
  "metadata": { "buildInvocationId": "${CI_PIPELINE_NUMBER:-unknown}" }
}
EOF
  if ! cosign attest --key "$COSIGN_KEY" --yes \
        --type slsaprovenance --predicate "$pred" "$img" >/dev/null 2>&1; then
    printf 'ATTEST FAILED: cosign could not attach SLSA provenance to %s\n' "$img" >&2
    return 1
  fi
  printf 'OK — SLSA provenance attested for %s\n' "$img"
}

# ── verification (read-only) ─────────────────────────────────────────────────
verify() {
  local img="$1"
  need cosign
  [ -n "${COSIGN_PUBKEY:-}" ] || die "LANE BROKEN: COSIGN_PUBKEY is unset — cannot verify."
  if ! cosign verify --key "$COSIGN_PUBKEY" "$img" >/dev/null 2>&1; then
    # EXIT 1, NOT 2. We looked and the answer was no — that is a finding, not a broken step.
    printf 'UNVERIFIED: %s has no matching signature for the configured key.\n' "$img" >&2
    return 1
  fi
  printf 'OK — signature verified for %s\n' "$img"
}

# ── licences ─────────────────────────────────────────────────────────────────
licenses() {
  local img="$1"
  need trivy
  # `--scanners license` is a DIFFERENT question from trivy's vulnerability scan, which the
  # scan-suite already runs. Licence compliance had no tool at all in this estate before B88.
  if ! trivy image --scanners license --quiet "$img" >/dev/null 2>&1; then
    printf 'LICENSE FINDINGS: trivy reported licence issues for %s\n' "$img" >&2
    return 1
  fi
  printf 'OK — no licence findings for %s\n' "$img"
}

main() {
  [ $# -ge 1 ] || usage
  local cmd="$1"; shift
  case "$cmd" in
    sbom|sign|attest|verify|licenses)
      [ $# -ge 1 ] || die "usage: supply-chain.sh $cmd <image-ref>"
      "$cmd" "$1" ;;
    all)
      [ $# -ge 1 ] || die "usage: supply-chain.sh all <image-ref>"
      local rc=0
      sbom "$1"     || rc=$?
      sign "$1"     || rc=$?
      attest "$1"   || rc=$?
      licenses "$1" || rc=$?
      exit "$rc" ;;
    *)
      die "unknown subcommand: '$cmd'
valid: sbom sign attest verify licenses all" ;;
  esac
}

main "$@"
