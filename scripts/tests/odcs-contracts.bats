#!/usr/bin/env bats
# B157 / B158 follow-up E — ODCS data-contract conformance guard.
#
# The mesh had contract SUBSTANCE (dbt tests, Soda, DataHub DataContracts) but no single declarative
# contract and nothing that FAILED on a malformed one. This guards the adopted ODCS subset: every
# `*.odcs.yaml` must carry the required fundamentals. Like the coverage guards it FAILS CLOSED —
# a missing contracts root or a broken toolchain is exit 2 (could-not-run), never a clean pass.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-odcs-contracts.sh"
}

teardown() {
  teardown_stubs
}

lib_source() {
  ODCS_CONTRACTS_LIB=1 source "$GUARD"
}

# A minimal conformant contract as JSON (what yaml_to_json emits), for validate_doc unit tests.
_valid_json() {
  cat <<'JSON'
{"apiVersion":"v3.0.0","kind":"DataContract","id":"x","name":"X","version":"1.0.0","status":"active",
 "domain":"finance","dataProduct":"X","description":{"purpose":"p"},
 "servers":[{"server":"trino"}],
 "schema":[{"name":"t","properties":[{"name":"c","logicalType":"string"}]}],
 "team":[{"role":"owner","username":"e"}]}
JSON
}

@test "the guard exists and is executable" {
  [ -f "$GUARD" ]
  [ -x "$GUARD" ]
}

@test "validate_doc: a conformant contract yields no errors" {
  lib_source
  run validate_doc "$(_valid_json)"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "validate_doc: a wrong kind is flagged" {
  lib_source
  run validate_doc "$(_valid_json | sed 's/"DataContract"/"Widget"/')"
  [[ "$output" == *"kind must be DataContract"* ]]
}

@test "validate_doc: a non-semver version is flagged" {
  lib_source
  run validate_doc "$(_valid_json | sed 's/"1.0.0"/"1.0"/')"
  [[ "$output" == *"version must be semver"* ]]
}

@test "validate_doc: a schema table with no properties is flagged" {
  lib_source
  run validate_doc '{"apiVersion":"v3.0.0","kind":"DataContract","id":"x","name":"X","version":"1.0.0","status":"active","domain":"finance","dataProduct":"X","description":{"purpose":"p"},"servers":[{"server":"t"}],"schema":[{"name":"t","properties":[]}],"team":[{"role":"owner"}]}'
  [[ "$output" == *"no properties"* ]]
}

@test "validate_doc: a missing owner role is flagged" {
  lib_source
  run validate_doc "$(_valid_json | sed 's/"owner"/"reader"/')"
  [[ "$output" == *"role owner is required"* ]]
}

@test "main: a directory of conformant contracts exits 0" {
  mkdir -p "$BATS_TEST_TMPDIR/c"
  _valid_json > "$BATS_TEST_TMPDIR/c/ok.odcs.yaml"   # valid JSON is also valid YAML
  CONTRACTS_ROOT="$BATS_TEST_TMPDIR/c" run "$GUARD"
  [ "$status" -eq 0 ]
}

@test "main: a malformed contract exits 1" {
  mkdir -p "$BATS_TEST_TMPDIR/c"
  _valid_json | sed 's/"1.0.0"/"nope"/' > "$BATS_TEST_TMPDIR/c/bad.odcs.yaml"
  CONTRACTS_ROOT="$BATS_TEST_TMPDIR/c" run "$GUARD"
  [ "$status" -eq 1 ]
}

@test "main: two contracts sharing an id are flagged (exit 1)" {
  mkdir -p "$BATS_TEST_TMPDIR/c"
  _valid_json > "$BATS_TEST_TMPDIR/c/a.odcs.yaml"
  _valid_json > "$BATS_TEST_TMPDIR/c/b.odcs.yaml"   # same id "x"
  CONTRACTS_ROOT="$BATS_TEST_TMPDIR/c" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"duplicate id"* ]]
}

@test "main: a missing contracts root FAILS CLOSED as exit 2, not a clean pass" {
  CONTRACTS_ROOT="$BATS_TEST_TMPDIR/does-not-exist" run "$GUARD"
  [ "$status" -eq 2 ]
}
