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

@test "live spec identical to the snapshot → OK, called IDENTICAL (exit 0)" {
  # key order must not matter: re-serialise with sorted keys
  python3 -c "import json;json.dump(json.load(open('$SPECS/svc.openapi.json')),open('$LIVE','w'),sort_keys=True)"
  api "$LIVE"
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 0 ]
  [[ "$output" == *"1 identical, 0 additive drift, 0 skipped"* ]]
}

# B208 (2026-10-13): additive drift used to pass as "match" — the tool-server served an optional `langfuse` field for two
# weeks that its committed snapshot lacked, and the job printed "6 reachable API(s) match their committed contract".
# Now any difference is a finding: additive drift posts a WARNING alert (ApiContractStale) to Alertmanager; breaking
# drift still exits 1. ALERTMANAGER_URL=file://… is the test seam (the alert JSON is written there instead of POSTed).
additive_live() {
  python3 -c "
import json; d=json.load(open('$SPECS/svc.openapi.json'))
d['paths']['/c']={'get':{'responses':{'200':{}}}}
d['paths']['/b']['post']['responses']['403']={'description':'refused'}
json.dump(d,open('$LIVE','w'))"
}

@test "an ADDITIVE difference is named, alerted as a warning, and never called a match (exit 0)" {
  additive_live; api "$LIVE"
  export ALERTMANAGER_URL="file://$BATS_TEST_TMPDIR/alert.json"
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ADDITIVE DRIFT svc"* ]]
  [[ "$output" == *"/c"* && "$output" == *"POST /b"* ]]
  [[ "$output" == *"0 identical, 1 additive drift"* ]]
  [[ "$output" != *"match"* ]]
  python3 - "$BATS_TEST_TMPDIR/alert.json" <<'PY'
import json, sys
alerts = json.load(open(sys.argv[1]))
a = alerts[0]
assert a["labels"]["alertname"] == "ApiContractStale" and a["labels"]["severity"] == "warning", a
assert a["labels"]["api"] == "svc" and "re-lock" in a["annotations"]["description"], a
PY
}

@test "additive drift that cannot be ALERTED is exit 2 — a finding nobody hears is not reported" {
  additive_live; api "$LIVE"
  unset ALERTMANAGER_URL
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 2 ]
  [[ "$output" == *"ALERTMANAGER_URL"* ]]
}

@test "an alert POST that fails is exit 2, not a quiet pass" {
  additive_live; api "$LIVE"
  export ALERTMANAGER_URL="http://127.0.0.1:1/api/v2/alerts"
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 2 ]
  [[ "$output" == *"could not send"* ]]
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

# OBSERVED 2026-10-13 (the first live run of the B208 logic): realm-of-agents builds its A2A card's `url` and
# `provider.url` from the request's host, so the drift job (which fetches via the .svc name) always sees the internal
# URL while the snapshot was captured via the public one. Those are deployment-relative, not contract: ignore them.
@test "an A2A card that differs only in its host-derived url fields is IDENTICAL, not drift" {
  python3 - "$SPECS/card.json" "$LIVE" <<'PY'
import json, sys
card = {"protocolVersion": "0.3.0", "name": "realm", "url": "https://realm.example/a2a",
        "provider": {"organization": "weyland", "url": "https://realm.example"}, "skills": [{"id": "s1"}]}
json.dump(card, open(sys.argv[1], "w"))
card["url"] = "http://realm.svc:8080/a2a"; card["provider"]["url"] = "http://realm.svc:8080"
json.dump(card, open(sys.argv[2], "w"))
PY
  printf 'apis:\n  - {id: card, kind: a2a, spec: docs/api/specs/card.json, spec_source: "%s"}\n' "$LIVE" > "$BATS_TEST_TMPDIR/apis.yaml"
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 0 ]
  [[ "$output" == *"1 identical, 0 additive drift"* ]]
}

@test "an A2A card whose SKILLS changed is still drift" {
  python3 - "$SPECS/card.json" "$LIVE" <<'PY'
import json, sys
card = {"protocolVersion": "0.3.0", "name": "realm", "url": "u", "skills": [{"id": "s1"}]}
json.dump(card, open(sys.argv[1], "w"))
card["skills"].append({"id": "s2"})
json.dump(card, open(sys.argv[2], "w"))
PY
  printf 'apis:\n  - {id: card, kind: a2a, spec: docs/api/specs/card.json, spec_source: "%s"}\n' "$LIVE" > "$BATS_TEST_TMPDIR/apis.yaml"
  export ALERTMANAGER_URL="file://$BATS_TEST_TMPDIR/alert.json"
  run python3 "$RUNNER" "$BATS_TEST_TMPDIR/apis.yaml" "$SPECS"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ADDITIVE DRIFT card"* ]]
}
