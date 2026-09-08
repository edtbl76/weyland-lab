#!/usr/bin/env bats
# B155 — the API breaking-change engine. Classifies changes between two specs BREAKING/COMPATIBLE by
# consumer-compatibility rules. exit 0 = no breaking, 1 = breaking, 2 = cannot compare (never silent).
# Tests assert the REASON in the output, not just the exit code.

setup() {
  load helper
  ENGINE="$REPO_ROOT/scripts/lib/api_spec_diff.py"
  SPECS="$REPO_ROOT/docs/api/specs"
  OLD="$BATS_TEST_TMPDIR/old.json"
  NEW="$BATS_TEST_TMPDIR/new.json"
  # Build the fixture in python so it is guaranteed-valid JSON (a hand-written multi-line spec is fragile).
  python3 - "$OLD" <<'PY'
import json, sys
spec = {
  "openapi": "3.1.0", "info": {"title": "t", "version": "1.0.0"},
  "paths": {
    "/a": {"get": {
      "parameters": [{"name": "q", "in": "query", "required": True, "schema": {"enum": ["x", "y"]}}],
      "responses": {"200": {"content": {"application/json": {"schema": {"properties": {"f1": {}, "f2": {}}}}}}}}},
    "/b": {"post": {
      "requestBody": {"content": {"application/json": {"schema": {"properties": {"p": {}}, "required": ["p"]}}}},
      "responses": {"200": {"content": {"application/json": {"schema": {"properties": {"ok": {}}}}}}}}},
  }}
json.dump(spec, open(sys.argv[1], "w"))
PY
}

@test "the engine exists" { [ -f "$ENGINE" ]; }

@test "identical specs → OK (exit 0)" {
  run python3 "$ENGINE" "$OLD" "$OLD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "a new operation is COMPATIBLE (exit 0)" {
  python3 -c "import json;d=json.load(open('$OLD'));d['paths']['/c']={'get':{'responses':{'200':{}}}};json.dump(d,open('$NEW','w'))"
  run python3 "$ENGINE" "$OLD" "$NEW"
  [ "$status" -eq 0 ]
  [[ "$output" == *"operation added"* ]]
}

@test "a removed operation is BREAKING (exit 1, named)" {
  python3 -c "import json;d=json.load(open('$OLD'));del d['paths']['/a'];json.dump(d,open('$NEW','w'))"
  run python3 "$ENGINE" "$OLD" "$NEW"
  [ "$status" -eq 1 ]
  [[ "$output" == *"operation removed: GET /a"* ]]
}

@test "a new REQUIRED request-body field is BREAKING (exit 1)" {
  python3 -c "import json;d=json.load(open('$OLD'));d['paths']['/b']['post']['requestBody']['content']['application/json']['schema']['required']=['p','n'];json.dump(d,open('$NEW','w'))"
  run python3 "$ENGINE" "$OLD" "$NEW"
  [ "$status" -eq 1 ]
  [[ "$output" == *"became required"* ]]
}

@test "a removed response field is BREAKING (exit 1)" {
  python3 -c "import json;d=json.load(open('$OLD'));del d['paths']['/a']['get']['responses']['200']['content']['application/json']['schema']['properties']['f2'];json.dump(d,open('$NEW','w'))"
  run python3 "$ENGINE" "$OLD" "$NEW"
  [ "$status" -eq 1 ]
  [[ "$output" == *"response field 'f2' removed"* ]]
}

@test "a removed enum value is BREAKING (exit 1)" {
  python3 -c "import json;d=json.load(open('$OLD'));d['paths']['/a']['get']['parameters'][0]['schema']['enum']=['x'];json.dump(d,open('$NEW','w'))"
  run python3 "$ENGINE" "$OLD" "$NEW"
  [ "$status" -eq 1 ]
  [[ "$output" == *"enum value removed"* ]]
}

@test "A2A: a removed skill is BREAKING (exit 1)" {
  printf '%s' '{"protocolVersion":"0.3.0","skills":[{"id":"a"},{"id":"b"}]}' > "$OLD"
  printf '%s' '{"protocolVersion":"0.3.0","skills":[{"id":"a"}]}' > "$NEW"
  run python3 "$ENGINE" "$OLD" "$NEW"
  [ "$status" -eq 1 ]
  [[ "$output" == *"A2A skill removed: b"* ]]
}

@test "comparing different kinds is CANNOT-COMPARE (exit 2), never a silent pass" {
  printf '%s' '{"protocolVersion":"0.3.0","skills":[]}' > "$NEW"
  run python3 "$ENGINE" "$OLD" "$NEW"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT COMPARE"* ]]
}

@test "every committed snapshot is self-consistent (parses + diffs clean against itself)" {
  for f in "$SPECS"/*.json; do
    run python3 "$ENGINE" "$f" "$f"
    [ "$status" -eq 0 ]
  done
}
