#!/usr/bin/env bats
# B88 (image-signature follow-up) — declared-image provenance invariant.
#
# WHY THIS EXISTS: the Gatekeeper `require-signed-images` constraint is an INTERVAL AUDIT OF RUNNING
# PODS in dryrun. It cannot see an unreviewed image at COMMIT time (before anything deploys), and it
# cannot see a workload that is not currently running (a weekly CronJob, a scaled-to-zero store, a
# Deployment whose new image has not rolled). "0 violations at last audit" is therefore a transient
# OBSERVATION, not an INVARIANT — and it is the shakiest input to the eventual dryrun->deny flip.
#
# This guard makes it an invariant: every container/initContainer image DECLARED in the estate comes
# from a reviewed source — the `registry.weyland.lab/` allowlist, an official single-segment Docker Hub
# image, or one of the by-full-path reviewed publisher prefixes in image-signatures.yaml. It applies
# the SAME three-way logic as the constraint's Rego, reading the SAME policy file (single source of
# truth — never a hardcoded copy that drifts from the Rego).
#
# EXIT CODES are the contract. 0 = every declared image is reviewed. 1 = an unreviewed image appeared
# (named). 2 = the guard could not do its job (policy unparseable, no images found, empty fed list) —
# NEVER conflated with a clean estate, the same fail-closed rule the coverage guards enforce.
#
# The decision core is fed two ways (both exercised here): IMAGE_LIST (the CI git-manifest scan and the
# in-cluster kubectl enumerator both produce this) and POLICY_ALLOWED/POLICY_EXEMPT/POLICY_EXCLUDED_NS
# (fixtures that skip the policy-file parse). A test asserts the REASON in the output, never a bare exit.

setup() {
  load helper
  GUARD="$REPO_ROOT/scripts/check-image-provenance.sh"
  POLICY="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/gatekeeper/image-signatures.yaml"
}

lib_source() {
  IMAGE_PROVENANCE_LIB=1 source "$GUARD"
}

# A small, realistic policy shared by the lib/main cases.
export FIXTURE_ALLOWED=$'registry.weyland.lab/'
export FIXTURE_EXEMPT=$'docker.io/library/\nquay.io/\nghcr.io/\ndocker.io/grafana/\ngrafana/\nalpine/\ntrinodb/'

@test "the guard exists and is executable" {
  [ -f "$GUARD" ]
  [ -x "$GUARD" ]
}

@test "implicit_official: single-segment official images only" {
  lib_source
  implicit_official "postgres:18"            # library/postgres -> yes
  implicit_official "alpine:latest"
  implicit_official "registry:2.8.3"
  run implicit_official "grafana/grafana:11" # has a namespace -> NO (this was the historical bypass)
  [ "$status" -ne 0 ]
  run implicit_official "registry.weyland.lab/x:v1" # has a host segment -> NO
  [ "$status" -ne 0 ]
  run implicit_official "quay.io/coreos/etcd:v3" # host with a dot -> NO
  [ "$status" -ne 0 ]
}

@test "is_reviewed: allowlist, exempt prefixes, and implicit official all pass; an unknown org fails" {
  lib_source
  ALLOWED="$FIXTURE_ALLOWED"; EXEMPT="$FIXTURE_EXEMPT"
  is_reviewed "registry.weyland.lab/weyland-guard:v10"   # allowlist
  is_reviewed "docker.io/grafana/grafana:11"             # exempt full-path
  is_reviewed "grafana/pyroscope:1.9.0"                  # exempt publisher
  is_reviewed "trinodb/trino:468"                        # exempt publisher
  is_reviewed "postgres:18"                              # implicit official
  is_reviewed "alpine/git:latest"                        # exempt publisher
  run is_reviewed "docker.io/evilcorp/backdoor:latest"   # NOT reviewed
  [ "$status" -ne 0 ]
  run is_reviewed "somerandomuser/tool:latest"           # NOT reviewed (org-scoped Hub, unlisted)
  [ "$status" -ne 0 ]
}

@test "main: a fully-reviewed declared estate exits 0 with an OK line" {
  IMAGE_LIST=$'data-mesh\tregistry.weyland.lab/weyland-guard:v10\nweyland\tgrafana/pyroscope:1.9.0\ndefault\tpostgres:18' \
  POLICY_ALLOWED="$FIXTURE_ALLOWED" POLICY_EXEMPT="$FIXTURE_EXEMPT" \
    run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
  [[ "$output" == *"3"* ]]   # counts the declared images it cleared
}

@test "main: an unreviewed declared image exits 1 and NAMES it" {
  IMAGE_LIST=$'data-mesh\tregistry.weyland.lab/ok:v1\ndefault\tevilcorp/backdoor:latest' \
  POLICY_ALLOWED="$FIXTURE_ALLOWED" POLICY_EXEMPT="$FIXTURE_EXEMPT" \
    run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"evilcorp/backdoor:latest"* ]]
  [[ "$output" != *"registry.weyland.lab/ok:v1"* ]]   # the reviewed one is NOT reported
}

@test "main: an unreviewed image in an EXCLUDED namespace is skipped (exit 0)" {
  IMAGE_LIST=$'kube-system\tevilcorp/backdoor:latest\ndefault\tpostgres:18' \
  POLICY_ALLOWED="$FIXTURE_ALLOWED" POLICY_EXEMPT="$FIXTURE_EXEMPT" POLICY_EXCLUDED_NS=$'kube-system\nistio-system' \
    run "$GUARD"
  [ "$status" -eq 0 ]
}

@test "main: an EMPTY fed image list fails closed (exit 2), never a clean 0" {
  IMAGE_LIST="" POLICY_ALLOWED="$FIXTURE_ALLOWED" POLICY_EXEMPT="$FIXTURE_EXEMPT" run "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no declared images"* ]] || [[ "$output" == *"could not"* ]]
}

@test "main: an unreadable policy file fails closed (exit 2), never a clean 0" {
  IMAGE_LIST=$'default\tpostgres:18' POLICY_FILE="/nonexistent/policy.yaml" run "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"polic"* ]]
}

@test "the CronJob's embedded script is byte-identical to the tested guard" {
  # WHY: k8s/monitoring/image-provenance.yaml carries a COPY of the guard inside its ConfigMap so the
  # in-cluster enumerator runs the same decision core CI tests. Two copies drift silently on both sides.
  # The repo script is the source; scripts/embed-image-provenance.sh regenerates the embedded copy.
  local manifest="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/image-provenance.yaml"
  [ -f "$manifest" ]
  # Extract the 4-space-indented block under the `check-image-provenance.sh: |` data key, up to the
  # next `---` document separator, and strip exactly that indent.
  awk '
    $0 == "  check-image-provenance.sh: |" { grab=1; next }
    grab && $0 == "---" { grab=0 }
    grab { sub(/^    /, ""); print }
  ' "$manifest" > "$BATS_TEST_TMPDIR/embedded.sh"
  diff "$GUARD" "$BATS_TEST_TMPDIR/embedded.sh"
}

@test "main: parses the REAL policy file and judges against it" {
  # Feeds one image the real allowlist covers and one no reviewed publisher covers; proves the
  # python parse of the actual multi-doc image-signatures.yaml works, not just an injected fixture.
  [ -f "$POLICY" ]
  IMAGE_LIST=$'data-mesh\tregistry.weyland.lab/weyland-dagster-user-code:git-f5659901\ndefault\tunreviewedvendor/thing:latest' \
  POLICY_FILE="$POLICY" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"unreviewedvendor/thing:latest"* ]]
  [[ "$output" != *"weyland-dagster-user-code"* ]]
}
