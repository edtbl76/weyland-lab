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
  vuln      trivy --scanners vuln  (counts + Δ vs deployed baseline; NON-FATAL; exit 2 only if it cannot run)
  all       sbom -> sign -> attest -> licenses -> vuln (resilient: one broken step never aborts the rest)

  A second image ref (the currently-DEPLOYED image) may be passed to `vuln` or `all`; vuln then reports
  the DELTA — the CVEs the new image adds over the deployed one — instead of just an absolute count.

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
# scan_vuln <img> — print trivy's JSON report to stdout; return 0 if it scanned, 2 if it could not.
# `--skip-db-update` makes trivy use the DB the build step pre-warmed and FATAL-error if it is absent,
# so a missing DB is an honest exit-2 rather than a valid-looking 0-findings report (observed: a fresh
# install returned 0 for an image that had 327). The report-present guard (SchemaVersion + ArtifactName)
# uses here-strings, not `printf | grep -q`: under pipefail, grep -q short-circuits and SIGPIPEs a printf
# still streaming an 8 GB image's report, which would falsely mark a good scan broken.
scan_vuln() {
  local img="$1" out rc
  out="$(trivy image --scanners vuln --skip-db-update $TRIVY_INSECURE_FLAG --quiet --format json "$img" 2>&1)"; rc=$?
  printf '%s' "$out"
  { [ "$rc" -eq 0 ] && grep -q '"SchemaVersion"' <<<"$out" && grep -q '"ArtifactName"' <<<"$out"; } || return 2
}

# vuln_pairs — read a trivy JSON report on stdin, emit unique "CVE-ID SEVERITY" lines. VulnerabilityID
# and Severity are 1:1 and ID always precedes Severity within a finding (verified against live trivy),
# so awk pairs them without jq. sort -u collapses a CVE that hits multiple packages to one entry.
vuln_pairs() {
  awk '
    match($0,/"VulnerabilityID": *"[^"]+"/){ v=substr($0,RSTART,RLENGTH); gsub(/.*"VulnerabilityID": *"|"$/,"",v); id=v }
    match($0,/"Severity": *"[^"]+"/){ s=substr($0,RSTART,RLENGTH); gsub(/.*"Severity": *"|"$/,"",s); if(id!=""){print id" "s; id=""} }
  ' | sort -u
}

# vuln <img> [baseline-img] — scan <img> and report the CVE count (loud, NON-FATAL). When a baseline is
# given (the currently-DEPLOYED image), scan it too with the SAME pre-warmed DB and report the DELTA:
# the CVEs present in the new image but not the deployed one — i.e. what THIS change introduces, with
# CVE-disclosure drift controlled out because both were scanned now. A base-image CVE count is dominated
# by unchanged findings; the delta is the signal that a change added something. Still non-fatal — a loud,
# actionable line, not a merge blocker (gating on a new critical would be a one-line policy change here).
vuln() {
  local img="$1" base="${2:-}" newjson rc n crit high msg
  has trivy || { broken "\`trivy\` is not on PATH"; return 2; }
  newjson="$(scan_vuln "$img")"; rc=$?
  if [ "$rc" -ne 0 ]; then
    printf 'VULN SCAN BROKEN: trivy could not scan %s:\n%s\n' "$img" "$newjson" >&2
    return 2
  fi
  # grep -o | wc -l counts OCCURRENCES (a CVE per affected package), robust to compact or pretty JSON.
  n="$(grep -o '"VulnerabilityID"' <<<"$newjson" | wc -l | tr -d ' ')"
  crit="$(grep -oE '"Severity":[[:space:]]*"CRITICAL"' <<<"$newjson" | wc -l | tr -d ' ')"
  high="$(grep -oE '"Severity":[[:space:]]*"HIGH"' <<<"$newjson" | wc -l | tr -d ' ')"
  msg="OK — vuln scan $img: $n finding(s) [CRITICAL $crit · HIGH $high]"

  if [ -n "$base" ]; then
    local basejson brc newp oldp introduced ic ih itot
    basejson="$(scan_vuln "$base")"; brc=$?
    if [ "$brc" -ne 0 ]; then
      msg="$msg — Δ vs deployed: baseline $base could not be scanned, absolute count only"
    else
      newp="$(vuln_pairs <<<"$newjson")"
      oldp="$(vuln_pairs <<<"$basejson")"
      # introduced = new "ID SEV" lines whose CVE ID is not among the deployed image's IDs.
      introduced="$(awk 'NR==FNR{o[$1]=1;next} !($1 in o)' <(printf '%s\n' "$oldp") <(printf '%s\n' "$newp"))"
      itot=0; ic=0; ih=0
      if [ -n "$introduced" ]; then
        itot="$(grep -c . <<<"$introduced")"
        ic="$(grep -c ' CRITICAL$' <<<"$introduced" || true)"
        ih="$(grep -c ' HIGH$' <<<"$introduced" || true)"
      fi
      if [ "$itot" -gt 0 ]; then
        msg="$msg — Δ vs deployed: +$itot NEW CVE(s) this change ($ic CRITICAL, $ih HIGH)"
        if [ $((ic + ih)) -gt 0 ]; then
          printf '⚠ VULN DELTA — this change INTRODUCES %s CRITICAL + %s HIGH new CVE(s) into %s:\n' "$ic" "$ih" "$img" >&2
          grep -E ' (CRITICAL|HIGH)$' <<<"$introduced" | sed 's/^/    /' >&2
        fi
      else
        msg="$msg — Δ vs deployed: no new CVEs introduced by this change"
      fi
    fi
  fi
  # NON-FATAL: the count and the delta are reported; only a scan that could not run is exit 2.
  printf '%s — reported, non-blocking\n' "$msg"
}

# all <img> [baseline] — run every step, collect the WORST outcome (2 broken > 1 found > 0 clean),
# abort NOTHING. Only vuln takes the baseline (the deployed image, for the delta); the rest ignore it.
run_all() {
  local img="$1" base="${2:-}" worst=0 rc step
  for step in sbom sign attest licenses; do
    "$step" "$img"; rc=$?
    [ "$rc" -gt "$worst" ] && worst="$rc"
  done
  vuln "$img" "$base"; rc=$?
  [ "$rc" -gt "$worst" ] && worst="$rc"
  return "$worst"
}

main() {
  [ $# -ge 1 ] || usage
  local cmd="$1"; shift
  case "$cmd" in
    sbom|sign|attest|verify|licenses)
      [ $# -ge 1 ] || { printf 'usage: supply-chain.sh %s <image-ref>\n' "$cmd" >&2; exit 2; }
      "$cmd" "$1"; exit $? ;;
    vuln)
      [ $# -ge 1 ] || { printf 'usage: supply-chain.sh vuln <image-ref> [baseline-image-ref]\n' >&2; exit 2; }
      vuln "$1" "${2:-}"; exit $? ;;
    all)
      [ $# -ge 1 ] || { printf 'usage: supply-chain.sh all <image-ref> [baseline-image-ref]\n' >&2; exit 2; }
      run_all "$1" "${2:-}"; exit $? ;;
    *)
      printf 'unknown subcommand: %s\nvalid: sbom sign attest verify licenses vuln all\n' "$cmd" >&2
      exit 2 ;;
  esac
}

main "$@"
