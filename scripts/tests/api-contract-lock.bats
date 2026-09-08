#!/usr/bin/env bats
# B155 — the contract lock: PR-time breaking-change enforcement. The generator (gen-api-contract-lock.sh)
# records each snapshot-backed API's approved baseline + version and REFUSES to re-lock a breaking change
# that skipped a major bump; the guard (check-api-lifecycle.sh) fails when the lock is stale. Together a
# breaking contract change cannot ship without a major version bump. Tests use a temp tree (API_LOCK_ROOT).

setup() {
  load helper
  GEN="$REPO_ROOT/scripts/gen-api-contract-lock.sh"
  GUARD="$REPO_ROOT/scripts/check-api-lifecycle.sh"
  ROOT="$BATS_TEST_TMPDIR/root"
  mkdir -p "$ROOT/scripts/lib" "$ROOT/docs/api/specs" \
           "$ROOT/nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline"
  cp "$REPO_ROOT/scripts/lib/api_spec_diff.py" "$ROOT/scripts/lib/"
  APIS="$ROOT/nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline/apis.yaml"
  SPEC="$ROOT/docs/api/specs/svc.openapi.json"
  LOCK="$ROOT/docs/api/specs/contract-lock.json"
  # for the guard: a service registry so owners resolve
  REG="$BATS_TEST_TMPDIR/apps.yaml"
  printf 'applications:\n  - {key: svc, deployed: true, metrics: true, ingress: false, name: Svc, group: x, port_component: svc}\nexcluded: []\n' > "$REG"
  spec() { python3 - "$SPEC" "$1" <<'PY'
import json, sys
paths = {"/a": {"get": {"responses": {"200": {}}}}}
if sys.argv[2] == "two":
    paths["/b"] = {"post": {"responses": {"200": {}}}}
json.dump({"openapi": "3.1.0", "paths": paths}, open(sys.argv[1], "w"), indent=2, sort_keys=True)
PY
  }
  apis() { printf 'apis:\n  - {id: svc, owner: svc, kind: openapi, status: published, version: "%s", spec: docs/api/specs/svc.openapi.json}\n' "$1" > "$APIS"; }
}

@test "generator: first run writes the lock (exit 0)" {
  spec two; apis "1.0"
  API_LOCK_ROOT="$ROOT" run "$GEN"
  [ "$status" -eq 0 ]
  [ -f "$LOCK" ]
  [[ "$output" == *"locked 1 contract"* ]]
}

@test "generator: an additive change re-locks freely (exit 0)" {
  spec two; apis "1.0"; API_LOCK_ROOT="$ROOT" "$GEN" >/dev/null
  python3 -c "import json;d=json.load(open('$SPEC'));d['paths']['/c']={'get':{'responses':{'200':{}}}};json.dump(d,open('$SPEC','w'),indent=2,sort_keys=True)"
  API_LOCK_ROOT="$ROOT" run "$GEN"
  [ "$status" -eq 0 ]
}

@test "generator: a BREAKING change without a major bump is REFUSED (exit 1, named)" {
  spec two; apis "1.0"; API_LOCK_ROOT="$ROOT" "$GEN" >/dev/null
  python3 -c "import json;d=json.load(open('$SPEC'));del d['paths']['/b'];json.dump(d,open('$SPEC','w'),indent=2,sort_keys=True)"   # remove op = breaking
  API_LOCK_ROOT="$ROOT" run "$GEN"        # version still 1.0
  [ "$status" -eq 1 ]
  [[ "$output" == *"REFUSED"* ]]
  [[ "$output" == *"operation removed: POST /b"* ]]
}

@test "generator: a BREAKING change WITH a major bump re-locks (exit 0)" {
  spec two; apis "1.0"; API_LOCK_ROOT="$ROOT" "$GEN" >/dev/null
  python3 -c "import json;d=json.load(open('$SPEC'));del d['paths']['/b'];json.dump(d,open('$SPEC','w'),indent=2,sort_keys=True)"
  apis "2.0"                              # major bump
  API_LOCK_ROOT="$ROOT" run "$GEN"
  [ "$status" -eq 0 ]
  [[ "$output" == *"locked"* ]]
}

@test "guard: a snapshot changed vs its locked baseline fails the LOCK check (exit 1)" {
  spec two; apis "1.0"; API_LOCK_ROOT="$ROOT" "$GEN" >/dev/null
  python3 -c "import json;d=json.load(open('$SPEC'));del d['paths']['/b'];json.dump(d,open('$SPEC','w'),indent=2,sort_keys=True)"
  APIS_FILE="$APIS" REGISTRY_FILE="$REG" SPECS_DIR="$ROOT/docs/api/specs" run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"LOCK"* ]]
  [[ "$output" == *"locked baseline"* ]]
}

@test "the REAL catalog's lock is current (the live invariant)" {
  run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"snapshotted + locked"* ]]
}
