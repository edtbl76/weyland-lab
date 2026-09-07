#!/usr/bin/env bats
# B154 — onboarding-completeness guard: the full DoD §6 checklist, declare + account.
#
# Each deployed service DECLARES which conditional gates apply (metrics/ingress). The guard VERIFIES the
# file-checkable gates (SCHEMA: deployed + metrics + ingress declared; PORT: port_component; PLACEMENT:
# a real LikeC4 element) and ACCOUNTS the rest in a per-service matrix (--list): metrics→ServiceMonitor/
# dashboard and *Down alert are LIVE (owned by the coverage guards), Kuma is MANUAL (UI), logs AUTO
# (Alloy), arch §6 curated. An undeclared conditional gate is an UNACCOUNTED gate → fail. Fail-closed:
# exit 1 = a defect (named), exit 2 = the guard could not run. Tests assert the REASON, never a bare exit.

setup() {
  load helper
  GUARD="$REPO_ROOT/scripts/check-onboarding-completeness.sh"
  MODEL="$BATS_TEST_TMPDIR/model.likec4"
  cat >"$MODEL" <<'EOF'
model {
  svcA = component "Service A" "a component"
  gw = gateway "Some Gateway" "a custom kind"
  dagster = component "Dagster" "orchestrator that subsumes dbt"
}
EOF
}

reg() { printf '%s\n' "applications:" "$@" > "$BATS_TEST_TMPDIR/reg.yaml"; }
REG() { echo "$BATS_TEST_TMPDIR/reg.yaml"; }

@test "the guard exists and is executable" {
  [ -f "$GUARD" ]
  [ -x "$GUARD" ]
}

@test "OK: a deployed service that declares metrics+ingress, has a port_component and a placement, exits 0" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, metrics: true, ingress: false, port_component: svca}" \
      "  - {key: some-gateway, name: Some Gateway, group: x, deployed: true, metrics: false, ingress: true, port_component: some-gateway}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
  [[ "$output" == *"onboarding-complete"* ]]
}

@test "PLACEMENT: a deployed service with no matching element exits 1 and NAMES it" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, metrics: false, ingress: false, port_component: svca}" \
      "  - {key: ghost, name: Ghost Service, group: x, deployed: true, metrics: false, ingress: false, port_component: ghost}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"UNPLACED"* ]]
  [[ "$output" == *"ghost"* ]]
}

@test "SCHEMA: an entry missing the boolean deployed field is a defect (exit 1), not a silent skip" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, metrics: false, ingress: false, port_component: svca}" \
      "  - {key: undeclared, name: Undeclared, group: x, port_component: undeclared}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"SCHEMA"* ]]
  [[ "$output" == *"undeclared"* ]]
}

@test "SCHEMA: a deployed service that does NOT declare metrics/ingress is an unaccounted gate (exit 1)" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, port_component: svca}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"SCHEMA"* ]]
  [[ "$output" == *"metrics"* ]]
}

@test "PORT: a deployed service with no port_component is a defect (exit 1)" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, metrics: false, ingress: false}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"PORT"* ]]
  [[ "$output" == *"svca"* ]]
}

@test "override: likec4:<id> present in the model resolves a subsumed/renamed service (exit 0)" {
  reg "  - {key: dbt, name: dbt, group: x, deployed: true, metrics: true, ingress: false, likec4: dagster, port_component: dbt}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 0 ]
}

@test "override: a likec4:<id> that is NOT in the model is drift (exit 1, distinct reason)" {
  reg "  - {key: bad, name: Bad, group: x, deployed: true, metrics: false, ingress: false, likec4: doesnotexist, port_component: bad}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"doesnotexist"* ]]
  [[ "$output" == *"not in the model"* ]]
}

@test "deployed:false is skipped — a non-deployed service needs no element, port, or gate declaration" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, metrics: false, ingress: false, port_component: svca}" \
      "  - {key: some-saas, name: Some SaaS, group: code-review, deployed: false}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 0 ]
}

@test "--list emits the per-service DoD §6 matrix accounting every gate" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, metrics: true, ingress: true, port_component: svca}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"svca"* ]]
  [[ "$output" == *"LIVE"* ]]      # metrics/alert accounted to the live guards
  [[ "$output" == *"MANUAL"* ]]    # ingress→Kuma accounted as manual
  [[ "$output" == *"AUTO"* ]]      # logs accounted as automatic
}

@test "fail closed: an unreadable registry is CANNOT-RUN (exit 2), never a clean 0" {
  REGISTRY_FILE="/nonexistent/reg.yaml" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT RUN"* ]]
}

@test "fail closed: a registry with no applications is exit 2, never a clean 0" {
  printf 'other: []\n' > "$BATS_TEST_TMPDIR/reg.yaml"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 2 ]
}

@test "fail closed: a model with no parseable elements is exit 2, never 'all unplaced'" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, metrics: false, ingress: false, port_component: svca}"
  printf 'model {}\n' > "$BATS_TEST_TMPDIR/empty.likec4"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$BATS_TEST_TMPDIR/empty.likec4" run "$GUARD"
  [ "$status" -eq 2 ]
}

@test "the REAL registry and model are onboarding-complete (the live invariant)" {
  run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}
