#!/usr/bin/env bats
# B154 Phase 1a/extension — onboarding-completeness guard.
#
# The coverage family proves a service is scraped/visualized/alerted/cataloged/registered; this guard
# proves a DEPLOYED service is onboarding-complete in the files: it declares a boolean `deployed`
# (SCHEMA — a missing field would silently skip it), it declares a `port_component` (PORT), and it
# resolves to a real LikeC4 element (PLACEMENT). Fail-closed: exit 1 = a defect (named), exit 2 = the
# guard could not run (registry/model unreadable/empty). Tests assert the REASON, never a bare exit.

setup() {
  load helper
  GUARD="$REPO_ROOT/scripts/check-onboarding-completeness.sh"
  MODEL="$BATS_TEST_TMPDIR/model.likec4"
  cat >"$MODEL" <<'EOF'
model {
  svcA = component "Service A" "a component"
  gw = gateway "Some Gateway" "a custom kind"
  st = store "Some Store" "another kind"
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

@test "OK: deployed services placed (by id and by display-name) with a port_component exit 0" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, port_component: svca}" \
      "  - {key: some-gateway, name: Some Gateway, group: x, deployed: true, port_component: some-gateway}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "PLACEMENT: a deployed service with no matching element exits 1 and NAMES it" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, port_component: svca}" \
      "  - {key: ghost, name: Ghost Service, group: x, deployed: true, port_component: ghost}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"UNPLACED"* ]]
  [[ "$output" == *"ghost"* ]]
}

@test "SCHEMA: an entry missing the boolean deployed field is a defect (exit 1), not a silent skip" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, port_component: svca}" \
      "  - {key: undeclared, name: Undeclared, group: x, port_component: undeclared}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"SCHEMA"* ]]
  [[ "$output" == *"undeclared"* ]]
}

@test "PORT: a deployed service with no port_component is a defect (exit 1)" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"PORT"* ]]
  [[ "$output" == *"svca"* ]]
}

@test "override: likec4:<id> present in the model resolves a subsumed/renamed service (exit 0)" {
  reg "  - {key: dbt, name: dbt, group: x, deployed: true, likec4: dagster, port_component: dbt}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 0 ]
}

@test "override: a likec4:<id> that is NOT in the model is drift (exit 1, distinct reason)" {
  reg "  - {key: bad, name: Bad, group: x, deployed: true, likec4: doesnotexist, port_component: bad}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"doesnotexist"* ]]
  [[ "$output" == *"not in the model"* ]]
}

@test "deployed:false is skipped — a non-deployed service needs neither element nor port_component" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true, port_component: svca}" \
      "  - {key: some-saas, name: Some SaaS, group: code-review, deployed: false}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 0 ]
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
  reg "  - {key: svca, name: Service A, group: x, deployed: true, port_component: svca}"
  printf 'model {}\n' > "$BATS_TEST_TMPDIR/empty.likec4"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$BATS_TEST_TMPDIR/empty.likec4" run "$GUARD"
  [ "$status" -eq 2 ]
}

@test "the REAL registry and model are onboarding-complete (the live invariant)" {
  run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}
