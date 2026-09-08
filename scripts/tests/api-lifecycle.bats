#!/usr/bin/env bats
# B155 — API lifecycle governance guard over apis.yaml. Verifies schema (id/owner/kind/status/version),
# owner resolution, published typed contracts are snapshotted, deprecation completeness, retired-has-no-
# consumers. Fail-closed: exit 1 = a governance defect (named), exit 2 = the guard could not run. Tests
# assert the REASON, not just the exit code.

setup() {
  load helper
  GUARD="$REPO_ROOT/scripts/check-api-lifecycle.sh"
  REG="$BATS_TEST_TMPDIR/apps.yaml"
  SPECS="$BATS_TEST_TMPDIR/specs"
  mkdir -p "$SPECS"
  printf '{}' > "$SPECS/svc.openapi.json"
  # a contract lock matching the OK fixture's spec-backed API (id `a`, v1.0, spec {})
  printf '{"a": {"version": "1.0", "spec": {}}}' > "$SPECS/contract-lock.json"
  cat >"$REG" <<'EOF'
applications:
  - {key: svc, deployed: true, metrics: true, ingress: false, name: Svc, group: x, port_component: svc}
  - {key: gw, deployed: true, metrics: false, ingress: true, name: GW, group: gateway, port_component: gw}
excluded:
  - {key: pg, kind: store, reason: db}
EOF
}

api() { printf '%s\n' "apis:" "$@" > "$BATS_TEST_TMPDIR/apis.yaml"; }
run_guard() { APIS_FILE="$BATS_TEST_TMPDIR/apis.yaml" REGISTRY_FILE="$REG" SPECS_DIR="$SPECS" REPO_ROOT="$BATS_TEST_TMPDIR" run "$GUARD" "$@"; }

@test "the guard exists and is executable" { [ -f "$GUARD" ]; [ -x "$GUARD" ]; }

@test "OK: a well-governed catalog exits 0" {
  api "  - {id: a, owner: svc, kind: openapi, status: published, version: \"1.0\", spec: specs/svc.openapi.json, consumers: [gw]}" \
      "  - {id: b, owner: gw, kind: openai-compat, status: published, version: \"1.0\", consumers: []}"
  run_guard
  [ "$status" -eq 0 ]
  [[ "$output" == *"well-governed"* ]]
}

@test "SCHEMA: a missing field is a defect (exit 1)" {
  api "  - {id: a, owner: svc, kind: openapi, status: published}"
  run_guard
  [ "$status" -eq 1 ]
  [[ "$output" == *"SCHEMA"* ]]
  [[ "$output" == *"version"* ]]
}

@test "SCHEMA: an invalid kind/status is a defect (exit 1)" {
  api "  - {id: a, owner: svc, kind: grpc, status: live, version: \"1.0\"}"
  run_guard
  [ "$status" -eq 1 ]
  [[ "$output" == *"invalid kind"* ]] || [[ "$output" == *"invalid status"* ]]
}

@test "OWNER: an owner that is not a service is a defect (exit 1)" {
  api "  - {id: a, owner: ghostsvc, kind: openai-compat, status: published, version: \"1.0\"}"
  run_guard
  [ "$status" -eq 1 ]
  [[ "$output" == *"OWNER"* ]]
  [[ "$output" == *"ghostsvc"* ]]
}

@test "SPEC: a published openapi API with no snapshot is a defect (exit 1)" {
  api "  - {id: a, owner: svc, kind: openapi, status: published, version: \"1.0\"}"
  run_guard
  [ "$status" -eq 1 ]
  [[ "$output" == *"SPEC"* ]]
  [[ "$output" == *"no \`spec\` snapshot"* ]] || [[ "$output" == *"snapshot"* ]]
}

@test "SPEC: a published openapi API whose snapshot file is missing is a defect (exit 1)" {
  api "  - {id: a, owner: svc, kind: openapi, status: published, version: \"1.0\", spec: specs/nope.json}"
  run_guard
  [ "$status" -eq 1 ]
  [[ "$output" == *"missing on disk"* ]]
}

@test "DEPRECATION: deprecated without retire_by/successor is a defect (exit 1)" {
  api "  - {id: a, owner: svc, kind: openai-compat, status: deprecated, version: \"1.0\"}"
  run_guard
  [ "$status" -eq 1 ]
  [[ "$output" == *"DEPRECATION"* ]]
  [[ "$output" == *"retire_by"* ]]
}

@test "DEPRECATION: a well-formed deprecation pointing at a real successor passes (exit 0)" {
  api "  - {id: a, owner: svc, kind: openai-compat, status: deprecated, version: \"1.0\", consumers: [], deprecation: {retire_by: \"2026-12-31\", successor: b}}" \
      "  - {id: b, owner: gw, kind: openai-compat, status: published, version: \"2.0\"}"
  run_guard
  [ "$status" -eq 0 ]
}

@test "RETIRED: a retired API that still has consumers is a defect (exit 1)" {
  api "  - {id: a, owner: svc, kind: openai-compat, status: retired, version: \"1.0\", consumers: [gw]}"
  run_guard
  [ "$status" -eq 1 ]
  [[ "$output" == *"RETIRED"* ]]
}

@test "--list prints the lifecycle catalog and exits 0" {
  api "  - {id: a, owner: svc, kind: openapi, status: published, version: \"1.0\", spec: specs/svc.openapi.json}"
  run_guard --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"lifecycle catalog"* ]]
  [[ "$output" == *"published"* ]]
}

@test "fail closed: an unreadable catalog is exit 2, never a clean 0" {
  APIS_FILE="/nonexistent/apis.yaml" REGISTRY_FILE="$REG" SPECS_DIR="$SPECS" REPO_ROOT="$BATS_TEST_TMPDIR" run "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT RUN"* ]]
}

@test "fail closed: a catalog with no apis is exit 2" {
  printf 'other: []\n' > "$BATS_TEST_TMPDIR/apis.yaml"
  run_guard
  [ "$status" -eq 2 ]
}

@test "the REAL catalog is well-governed (the live invariant)" {
  run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}
