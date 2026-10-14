#!/usr/bin/env bats
# check-write-surfaces.sh — B209 (2026-10-14): every deployed service that can CHANGE STATE has a front door.
# The act guard covered three tool-server endpoints while the Dagster API, store-scaler and the Realm took writes from
# any pod. This guard keeps the class closed: a `writes: true` service needs a NetworkPolicy / AuthorizationPolicy
# selecting its pods, a stated `front_door` (the app authenticates writes itself), or an `accepted_gap` citing a
# backlog item. Every failure test asserts the REASON, not just a non-zero status.

load helper

setup() {
  GUARD="$REPO_ROOT/scripts/check-write-surfaces.sh"
  T="$(mktemp -d)"
  mkdir -p "$T/k8s/a" "$T/k8s/istio"
  cat > "$T/k8s/a/netpol.yaml" <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: svc-a-front-door-only, namespace: weyland }
spec:
  podSelector: { matchLabels: { app: svc-a } }
  policyTypes: [Ingress]
  ingress: [{ from: [{ podSelector: { matchLabels: { app: caller } } }] }]
EOF
  cat > "$T/k8s/istio/authz.yaml" <<'EOF'
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata: { name: svc-b-acts, namespace: weyland }
spec:
  selector: { matchLabels: { app: svc-b-pods } }
  action: DENY
  rules: [{ from: [{ source: { notPrincipals: ["x"] } }] }]
EOF
  export K8S_DIR="$T/k8s" REGISTRY_FILE="$T/apps.yaml"
}

teardown() { rm -rf "$T"; }

reg() { printf 'applications:\n' > "$REGISTRY_FILE"; for line in "$@"; do printf '  - %s\n' "$line" >> "$REGISTRY_FILE"; done; }

@test "the guard exists" {
  [ -f "$GUARD" ]
}

@test "OK: a NetworkPolicy, an AuthorizationPolicy (via pod_app), a front_door and a read-only service all pass" {
  reg "{key: svc-a, deployed: true, writes: true}" \
      "{key: svc-b, deployed: true, writes: true, pod_app: svc-b-pods}" \
      "{key: svc-c, deployed: true, writes: true, front_door: 'Keycloak OIDC enforced by the app'}" \
      "{key: svc-d, deployed: true, writes: false}" \
      "{key: saas, deployed: false}"
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"4 deployed"* ]]
}

@test "a policy selecting by app.kubernetes.io/name (Helm charts) covers the service too" {
  cat > "$T/k8s/a/helm-netpol.yaml" <<'EOF2'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: chart-front-door-only, namespace: opensearch }
spec:
  podSelector: { matchLabels: { app.kubernetes.io/name: chart-ui } }
  policyTypes: [Ingress]
  ingress: [{ from: [{ podSelector: { matchLabels: { app: caller } } }] }]
EOF2
  reg "{key: chart, deployed: true, writes: true, pod_app: chart-ui}"
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "OPEN: a writes:true service with no policy, front door or accepted gap fails, named" {
  reg "{key: svc-open, deployed: true, writes: true}"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"svc-open"* && "$output" == *"no front door"* ]]
}

@test "SCHEMA: a deployed service that does not declare writes is a defect, not a silent pass" {
  reg "{key: svc-undeclared, deployed: true}"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"svc-undeclared"* && "$output" == *"declare writes"* ]]
}

@test "SCHEMA: writes must be a boolean ('yes' is not accepted)" {
  reg "{key: svc-y, deployed: true, writes: 'yes'}"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"svc-y"* && "$output" == *"boolean"* ]]
}

@test "an accepted_gap passes only when it cites a backlog item, and it is listed, not hidden" {
  reg "{key: svc-gap, deployed: true, writes: true, accepted_gap: 'B999: MLflow API unauthenticated until the B999 fix'}"
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"svc-gap"* && "$output" == *"B999"* ]]
}

@test "an accepted_gap with no backlog reference fails" {
  reg "{key: svc-gap, deployed: true, writes: true, accepted_gap: 'we will fix it later'}"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"svc-gap"* && "$output" == *"backlog"* ]]
}

@test "an empty front_door does not count" {
  reg "{key: svc-e, deployed: true, writes: true, front_door: ''}"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"svc-e"* ]]
}

@test "a policy for a DIFFERENT app does not cover the service (no label, no cover)" {
  reg "{key: svc-z, deployed: true, writes: true}"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"svc-z"* ]]
}

@test "fail closed: an unreadable registry is exit 2, never a clean 0" {
  export REGISTRY_FILE="$T/missing.yaml"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"registry"* ]]
}

@test "fail closed: a registry with no applications is exit 2" {
  printf 'applications: []\n' > "$REGISTRY_FILE"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
}

@test "fail closed: a manifest tree with no policies at all is exit 2 (the scan found nothing to compare)" {
  rm -f "$T/k8s/a/netpol.yaml" "$T/k8s/istio/authz.yaml"
  reg "{key: svc-a, deployed: true, writes: true}"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no NetworkPolicy"* ]]
}

@test "--list prints every deployed service with its verdict" {
  reg "{key: svc-a, deployed: true, writes: true}" "{key: svc-d, deployed: true, writes: false}"
  run bash "$GUARD" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"svc-a"*"policy"* && "$output" == *"svc-d"*"read-only"* ]]
}

@test "the REAL registry: every deployed write surface is covered or a tracked gap (the live invariant)" {
  unset K8S_DIR REGISTRY_FILE
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
