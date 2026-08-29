#!/usr/bin/env bash
#
# supply-chain.sh — SBOM, signing, provenance, licences and vulnerabilities for the images this lab
# ships (B88 Ph3 + gap #3).
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
#                     WHICH commit.
#   verify <image>    cosign verify against the public key. The read-only half.
#   licenses <image>  trivy's licence scanner (`--scanners license`) — a compliance question.
#   vuln <image>      trivy's VULNERABILITY scanner (`--scanners vuln`) per pushed image (gap #3).
#                     Weekly scan-suite trivy meant a base-image CVE shipped and sat until Sunday.
#                     LOUD BUT NON-FATAL: it prints the CVE count and exits 0 even WITH findings —
#                     gating every build on a base-image CVE (base images always carry some) would
#                     mute the gate, the same permanently-lit-alert argument this repo keeps making.
#                     Only a scan that COULD NOT RUN is exit 2.
#   all <image>       sbom -> sign -> attest -> licenses -> vuln. RESILIENT: one broken step (e.g. a
#                     missing COSIGN_KEY) no longer aborts the rest — every independent step runs and
#                     `all` returns the worst outcome. Before gap #3, sign's hard-exit on a missing
#                     key meant licences and vuln NEVER ran in CI.
#
# EXIT CODES
#   0  the step ran and reported clean
#   1  the step ran and FOUND something (a failed signature, a licence violation)
#   2  the step COULD NOT RUN — missing tool, missing key, unscannable image, bad arguments
# 1 and 2 are not interchangeable: "we looked and it is unsigned" and "we never looked" are
# different facts, and this repo has repeatedly shipped the second while reporting the first. Steps
# `return` these codes (they NEVER `exit` mid-run) so `all` can collect them without being aborted.
#
# INSECURE REGISTRY. registry.weyland.lab is HTTPS with a mkcert cert the tools don't trust
# (nodes' registries.yaml `insecure_skip_verify`, and buildctl pushes with `registry.insecure=true`).
# syft and trivy must skip TLS verification to pull the just-pushed image, or every scan is "broken".
#
# NOTHING HERE ENFORCES. Signing an image cannot break a running cluster; REQUIRING a signature can.
# Admission control lives in k8s/gatekeeper/image-signatures.yaml and ships in `dryrun`.
set -uo pipefail

SBOM_DIR="${WEYLAND_SBOM_DIR:-${TMPDIR:-/tmp}/weyland-sbom}"

# Skip TLS verify when syft pulls from the lab registry (the trivy equivalent is the --insecure flag,
# passed per-invocation below). Overridable so a test or a public-registry run can turn it off.
export SYFT_REGISTRY_INSECURE_SKIP_TLS_VERIFY="${SYFT_REGISTRY_INSECURE_SKIP_TLS_VERIFY:-true}"
TRIVY_INSECURE_FLAG="${WEYLAND_TRIVY_INSECURE_FLAG:---insecure}"

# broken <msg> — print a LANE BROKEN line. Callers RETURN 2 right after (a step must return, never
# exit, so `all` is not aborted). Kept print-only so it composes as `... || { broken "x"; return 2; }`.
broken() { printf 'LANE BROKEN: %s\n' "$*" >&2; }

usage() {
  cat >&2 <<'EOF'
usage: supply-chain.sh <sbom|sign|attest|verify|licenses|vuln|all> <image-ref>

  sbom      syft -> CycloneDX + SPDX
  sign      cosign sign            (needs COSIGN_KEY)
  attest    cosign attest, SLSA provenance predicate (needs COSIGN_KEY)
  verify    cosign verify          (needs COSIGN_PUBKEY)
  licenses  trivy --scanners license
  vuln      trivy --scanners vuln  (counts, NON-FATAL; exit 2 only if it cannot run)
  all       sbom -> sign -> attest -> licenses -> vuln (resilient: one broken step never aborts the rest)

exit 0 clean · 1 found something · 2 could not run
EOF
  exit 2
}

# has <tool> — is it on PATH? Callers do `has x || return 2` so a missing tool breaks the STEP, not
# the whole script.
has() { command -v "$1" >/dev/null 2>&1; }

# ── SBOM ─────────────────────────────────────────────────────────────────────
sbom() {
  local img="$1" safe out err rc=0
  has syft || { broken "\`syft\` is not on PATH"; return 2; }
  safe="$(printf '%s' "$img" | tr '/:' '__')"
  mkdir -p "$SBOM_DIR"
  for fmt in cyclonedx-json spdx-json; do
    out="$SBOM_DIR/${safe}.${fmt%%-*}.json"
    # Capture syft's stderr rather than swallowing it: a failed SBOM was a blank "SBOM FAILED" line
    # with no cause. A syft that cannot produce an SBOM has not run -> broken (2), not a "finding".
    if ! err="$(syft "$img" -o "$fmt=$out" 2>&1 >/dev/null)"; then
      printf 'SBOM BROKEN: syft could not produce %s for %s:\n%s\n' "$fmt" "$img" "$err" >&2
      rc=2
    fi
  done
  [ "$rc" -eq 0 ] || return "$rc"
  printf 'OK — SBOM written for %s (cyclonedx + spdx) in %s\n' "$img" "$SBOM_DIR"
}

# ── signing ──────────────────────────────────────────────────────────────────
sign() {
  local img="$1"
  has cosign || { broken "\`cosign\` is not on PATH"; return 2; }
  # A missing key must NOT degrade to "did not sign, carried on". An unsigned image that reported
  # success is indistinguishable later from one whose signature was stripped.
  [ -n "${COSIGN_KEY:-}" ] || { broken "COSIGN_KEY is unset — refusing to 'sign' without a key (SealedSecret cosign-signing-key; see runbooks/supply-chain.md)"; return 2; }
  if ! cosign sign --key "$COSIGN_KEY" --yes "$img" >/dev/null 2>&1; then
    printf 'SIGN FAILED: cosign could not sign %s\n' "$img" >&2
    return 1
  fi
  printf 'OK — signed %s\n' "$img"
}

# ── provenance ───────────────────────────────────────────────────────────────
attest() {
  local img="$1" pred
  has cosign || { broken "\`cosign\` is not on PATH"; return 2; }
  [ -n "${COSIGN_KEY:-}" ] || { broken "COSIGN_KEY is unset — cannot attest"; return 2; }
  mkdir -p "$SBOM_DIR"
  pred="$SBOM_DIR/provenance.json"
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
  has cosign || { broken "\`cosign\` is not on PATH"; return 2; }
  [ -n "${COSIGN_PUBKEY:-}" ] || { broken "COSIGN_PUBKEY is unset — cannot verify"; return 2; }
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
  has trivy || { broken "\`trivy\` is not on PATH"; return 2; }
  # A licence FINDING is a real result (exit 1). --insecure so trivy can pull from the lab registry.
  if ! trivy image --scanners license $TRIVY_INSECURE_FLAG --quiet "$img" >/dev/null 2>&1; then
    printf 'LICENSE FINDINGS: trivy reported licence issues for %s\n' "$img" >&2
    return 1
  fi
  printf 'OK — no licence findings for %s\n' "$img"
}

# ── vulnerabilities (gap #3) ─────────────────────────────────────────────────
vuln() {
  local img="$1" out rc n crit high
  has trivy || { broken "\`trivy\` is not on PATH"; return 2; }
  out="$(trivy image --scanners vuln $TRIVY_INSECURE_FLAG --quiet --format json "$img" 2>&1)"; rc=$?
  # DID IT ACTUALLY SCAN? A real trivy report carries SchemaVersion + ArtifactName. A non-zero exit,
  # or output that is NOT a report, means trivy could not pull/scan -> broken (2). Reading "0 findings"
  # off a scan that never happened is the absence-as-success trap; 0 findings counts ONLY when the
  # report is present. Read what trivy PRINTED, never its exit code alone.
  # here-strings, NOT `printf | grep -q`: under `set -o pipefail`, grep -q short-circuits on the match
  # and closes the pipe, so a printf still streaming a huge report (an 8 GB image's JSON) gets SIGPIPE
  # (141) and pipefail reports the whole pipeline failed — the guard would then falsely call a perfectly
  # good scan "broken". A here-string has no pipe, so it is immune at any output size.
  if [ "$rc" -ne 0 ] || ! grep -q '"SchemaVersion"' <<<"$out" || ! grep -q '"ArtifactName"' <<<"$out"; then
    printf 'VULN SCAN BROKEN: trivy could not scan %s (rc=%s):\n%s\n' "$img" "$rc" "$out" >&2
    return 2
  fi
  # grep -o | wc -l counts OCCURRENCES, not matching lines: trivy pretty-prints (one field per line)
  # but compact JSON would put many on one line, and `grep -c` would then undercount to 1. Robust to both.
  n="$(printf '%s\n' "$out" | grep -o '"VulnerabilityID"' | wc -l | tr -d ' ')"
  crit="$(printf '%s\n' "$out" | grep -oE '"Severity":[[:space:]]*"CRITICAL"' | wc -l | tr -d ' ')"
  high="$(printf '%s\n' "$out" | grep -oE '"Severity":[[:space:]]*"HIGH"' | wc -l | tr -d ' ')"
  # NON-FATAL: findings are COUNTS, not a gate (see the header). Exit 0 with the count.
  printf 'OK — vuln scan %s: %s finding(s) [CRITICAL %s · HIGH %s] — reported, non-blocking\n' \
    "$img" "$n" "$crit" "$high"
}

# all — run every step, collect the WORST outcome (2 broken > 1 found > 0 clean), abort NOTHING.
run_all() {
  local img="$1" worst=0 rc step
  for step in sbom sign attest licenses vuln; do
    "$step" "$img"; rc=$?
    [ "$rc" -gt "$worst" ] && worst="$rc"
  done
  return "$worst"
}

main() {
  [ $# -ge 1 ] || usage
  local cmd="$1"; shift
  case "$cmd" in
    sbom|sign|attest|verify|licenses|vuln)
      [ $# -ge 1 ] || { printf 'usage: supply-chain.sh %s <image-ref>\n' "$cmd" >&2; exit 2; }
      "$cmd" "$1"; exit $? ;;
    all)
      [ $# -ge 1 ] || { printf 'usage: supply-chain.sh all <image-ref>\n' >&2; exit 2; }
      run_all "$1"; exit $? ;;
    *)
      printf 'unknown subcommand: %s\nvalid: sbom sign attest verify licenses vuln all\n' "$cmd" >&2
      exit 2 ;;
  esac
}

main "$@"
