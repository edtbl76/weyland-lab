#!/usr/bin/env bats
# B154 Phase 1a — onboarding-completeness guard.
#
# WHY THIS EXISTS: the coverage family proves a service is scraped/visualized/alerted/cataloged/registered,
# but nothing proved a DEPLOYED service is PLACED in the single LikeC4 model — the exact drift the DoD
# flags and that bit the image-provenance CronJob on 2026-09-07. This guard closes it: every
# `deployed: true` registry entry must resolve to a real LikeC4 element, by an explicit `likec4: <id>`
# or a normalized key/name match. Fail-closed: exit 1 = an unplaced service (named), exit 2 = the guard
# could not run (registry/model unreadable/empty). Tests assert the REASON in the output, never a bare exit.

setup() {
  load helper
  GUARD="$REPO_ROOT/scripts/check-onboarding-completeness.sh"
  # A minimal LikeC4 model exercising all element kinds the extractor must accept.
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

@test "OK: every deployed service placed (by id and by display-name match) exits 0" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true}" \
      "  - {key: some-gateway, name: Some Gateway, group: x, deployed: true}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
  [[ "$output" == *"2"* ]]
}

@test "drift: a deployed service with no matching element exits 1 and NAMES it" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true}" \
      "  - {key: ghost, name: Ghost Service, group: x, deployed: true}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"UNPLACED"* ]]
  [[ "$output" == *"ghost"* ]]
  [[ "$output" != *"- svca"* ]]   # the placed one is not reported
}

@test "override: likec4:<id> present in the model resolves a subsumed/renamed service (exit 0)" {
  reg "  - {key: dbt, name: dbt, group: x, deployed: true, likec4: dagster}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 0 ]
}

@test "override: a likec4:<id> that is NOT in the model is drift (exit 1, distinct reason)" {
  reg "  - {key: bad, name: Bad, group: x, deployed: true, likec4: doesnotexist}"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$MODEL" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"doesnotexist"* ]]
  [[ "$output" == *"not in the model"* ]]
}

@test "deployed:false is skipped — a non-deployed service with no element does NOT fail" {
  reg "  - {key: svca, name: Service A, group: x, deployed: true}" \
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
  reg "  - {key: svca, name: Service A, group: x, deployed: true}"
  printf 'model {}\n' > "$BATS_TEST_TMPDIR/empty.likec4"
  REGISTRY_FILE="$(REG)" LIKEC4_FILE="$BATS_TEST_TMPDIR/empty.likec4" run "$GUARD"
  [ "$status" -eq 2 ]
}

@test "the REAL registry and model are in sync — every deployed service is placed (the live invariant)" {
  run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}
