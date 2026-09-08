#!/usr/bin/env bats
# B155 — live API drift check (the runtime half). Fetches each catalogued API's live spec and diffs it
# against the committed snapshot with the breaking-change engine. exit 0 = no breaking drift (unreachable
# sources skipped + listed), 1 = breaking drift (named), 2 = cannot run. A `spec_source` that is not
# http(s) is read as a local file, so these tests feed a 'live' spec without a network.

setup() {
  load helper
  RUNNER="$REPO_ROOT/scripts/lib/api_drift.py"
  SPECS="$BATS_TEST_TMPDIR/specs"; mkdir -p "$SPECS"
  # a committed snapshot
  python3 - "$SPECS/svc.openapi.json" <<'PY'
import json, sys
json.dump({"openapi": "3.1.0", "info": {"version": "1.0"},
           "paths": {"/a": {"get": {"responses": {"200": {}}}},
                     "/b": {"post": {"responses": {"200": {}}}}}}, open(sys.argv[1], "w"))
PY
  LIVE="$BATS_TEST_TMPDIR/live.json"
}

api() { printf 'apis:\n  - {id: svc, spec: docs/api/specs/svc.openapi.json, spec_source: "%s"}\n' "$1" > "$BATS_TEST_TMPDIR/apis.yaml"; }

@test "the runner exists" { [ -f "$RUNNER" ]; }

@test "live spec matching the snapshot → OK (exit 0)" {
  cp "$SPECS/svc.openapi.json" "$LIVE"
  api "$LIVE"
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 0 ]
  [[ "$output" == *"match their committed contract"* ]]
}

@test "live spec with an operation removed → BREAKING DRIFT (exit 1, named)" {
  python3 -c "import json;d=json.load(open('$SPECS/svc.openapi.json'));del d['paths']['/b'];json.dump(d,open('$LIVE','w'))"
  api "$LIVE"
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 1 ]
  [[ "$output" == *"BREAKING DRIFT"* ]]
  [[ "$output" == *"operation removed: POST /b"* ]]
}

@test "an unreachable source is SKIPPED, not drift (exit 0, listed)" {
  api "http://127.0.0.1:1/openapi.json"   # nothing listening → fetch fails
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 0 ]
  [[ "$output" == *"SKIP svc"* ]]
  [[ "$output" == *"unreachable"* ]]
}

@test "a missing snapshot for a catalogued API is CANNOT-RUN (exit 2)" {
  printf 'apis:\n  - {id: svc, spec: docs/api/specs/GONE.json, spec_source: "%s"}\n' "$SPECS/svc.openapi.json" > "$BATS_TEST_TMPDIR/apis.yaml"
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 2 ]
}

@test "the embedded ConfigMap copies are byte-identical to the repo engine + runner" {
  cm="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/api-drift-configmap.yaml"
  [ -f "$cm" ]
  # extract the two python blocks and diff them against the repo sources
  for f in api_spec_diff.py api_drift.py; do
    awk -v key="  $f: |" '
      $0 == key { grab=1; next }
      grab && /^  [A-Za-z0-9._-]+: \|/ { grab=0 }
      grab && $0 == "---" { grab=0 }
      grab { sub(/^    /, ""); print }
    ' "$cm" > "$BATS_TEST_TMPDIR/$f"
    diff "$REPO_ROOT/scripts/lib/$f" "$BATS_TEST_TMPDIR/$f"
  done
}
