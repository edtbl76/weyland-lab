#!/usr/bin/env bats
# B144 — the Port `githubPullRequest` reaper.
#
# WHY THIS IS THE MOST DANGEROUS SCRIPT IN THE pr-lifecycle DIRECTORY: its siblings only ever POST an
# alert. This one issues `DELETE /v1/blueprints/githubPullRequest/entities/<id>` against the live
# catalog. Every other watchdog's worst failure is a missed alert; this one's worst failure is
# deleting catalog data because GitHub returned a 502.
#
# So the tests are weighted accordingly: the majority assert that it does NOT delete. A reaper that
# reaps on a bad answer is worse than no reaper at all, and this repo has now shipped "an absent
# result read as a successful one" enough times that the bias has to be encoded, not remembered.
#
# The decision logic lives in the `port-pr-reconcile-logic` ConfigMap so the cluster runs the exact
# text this suite executes. Every external binary is stubbed onto PATH — nothing here reaches
# api.port.io or api.github.com.

setup() {
  load helper
  setup_stubs
  MANIFEST="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/pr-lifecycle/port-pr-reconcile.yaml"
  LOGIC="$STUB_DIR/port-pr-reconcile.sh"
  extract_configmap_script "$MANIFEST" "port-pr-reconcile.sh" > "$LOGIC"
  export PORT_CLIENT_ID=id PORT_CLIENT_SECRET=secret GITHUB_TOKEN=ghtok
}

teardown() {
  teardown_stubs
}

# lib_source — load the decision functions without running main.
#
# The two SIDE-EFFECTING operations are reached through indirection (`GH_STATE_FN` / `PORT_DELETE_FN`)
# so the suite can substitute a stub. A plain PATH stub would not work: a shell function always wins
# over an executable of the same name, so `gh_state` defined in the ConfigMap would silently shadow
# the stub and the test would exercise the real curl path while appearing to pass.
lib_source() {
  PORT_PR_REAP_LIB=1 source "$LOGIC"
  GH_STATE_FN=gh_state
  PORT_DELETE_FN=port_delete
  # Seed a valid token body by default. Without it every main() test silently exercises the REAL
  # curl in port_token and fails there — a red that looks exactly like "not implemented yet" under
  # TDD. A failing test's REASON has to be read, not just its colour; that is the same lesson as
  # `[ "$status" -ne 0 ]` passing on exit 127, pointed the other way.
  printf '{"accessToken":"test-token"}' > "$STUB_DIR/default-tok.json"
  export TOKEN_BODY="$STUB_DIR/default-tok.json"
}

@test "the manifest exists and the logic extracts from its ConfigMap" {
  [ -f "$MANIFEST" ]
  [ -s "$LOGIC" ]
  grep -q 'should_reap' "$LOGIC"
}

# --- should_reap: the single decision that authorises a DELETE -----------------------------------

@test "should_reap: a CLOSED pull request is reaped" {
  lib_source
  run should_reap "closed"
  [ "$status" -eq 0 ]
}

@test "should_reap: an OPEN pull request is NEVER reaped" {
  lib_source
  run should_reap "open"
  [ "$status" -ne 0 ]
}

@test "should_reap: an EMPTY state is NEVER reaped — the fail-closed case" {
  # This is the whole point. An unparseable response, a network blip, a changed field name — all of
  # them surface here as an empty string, and every one of them must mean "do not touch it".
  lib_source
  run should_reap ""
  [ "$status" -ne 0 ]
}

@test "should_reap: an UNRECOGNISED state is NEVER reaped" {
  # GitHub documents open/closed. If it ever returns something else, that is a reason to stop, not a
  # reason to guess — the same posture as cron_period_seconds refusing a schedule it cannot parse.
  lib_source
  run should_reap "draft"
  [ "$status" -ne 0 ]
}

# --- fetching: an absent answer is never a successful one ----------------------------------------

@test "github_pr_state: a 200 yields the state" {
  lib_source
  stub curl 0 '200'
  printf '{"state":"closed"}' > "$STUB_DIR/gh.json"
  GH_BODY="$STUB_DIR/gh.json"
  run github_pr_state "edtbl76/weyland-lab" 36
  [ "$status" -eq 0 ]
  [ "$output" = "closed" ]
}

@test "github_pr_state: a NON-200 fails, and emits no state" {
  lib_source
  stub curl 0 '502'
  printf 'gateway error' > "$STUB_DIR/gh.json"
  GH_BODY="$STUB_DIR/gh.json"
  run github_pr_state "edtbl76/weyland-lab" 36
  [ "$status" -ne 0 ]
  [[ "$output" != *"closed"* ]]
  [[ "$output" == *"502"* ]]
}

@test "github_pr_state: a curl TRANSPORT failure fails, and emits no state" {
  lib_source
  stub curl 7 ''
  run github_pr_state "edtbl76/weyland-lab" 36
  [ "$status" -ne 0 ]
  [[ "$output" == *"transport"* ]]
}

@test "port_token: a response with no accessToken is FATAL, not an empty token" {
  # An empty bearer would make every later call 401, and a 401-driven empty entity list would read
  # as "nothing to reap". Catch it at the source.
  lib_source
  stub curl 0 '200'
  printf '{"error":"nope"}' > "$STUB_DIR/tok.json"
  TOKEN_BODY="$STUB_DIR/tok.json"
  run port_token
  [ "$status" -ne 0 ]
  [[ "$output" == *"accessToken"* ]]
}

# --- the loop: what it does and, mostly, what it refuses to do -----------------------------------

# seed_entities <json> — stand up a fake Port entity listing for main() to consume.
seed_entities() {
  printf '%s' "$1" > "$STUB_DIR/entities.json"
  export ENTITIES_BODY="$STUB_DIR/entities.json"
}

TWO_ENTITIES='{"entities":[
  {"identifier":"111","properties":{"prNumber":36,"status":"open"},"relations":{"repository":"weyland-lab"}},
  {"identifier":"222","properties":{"prNumber":40,"status":"open"},"relations":{"repository":"stud.io"}}
]}'

@test "main: deletes ONLY the entity whose PR is closed on GitHub" {
  lib_source
  seed_entities "$TWO_ENTITIES"
  # 36 closed, 40 still open.
  stub_dispatch gh_state
  stub_case gh_state 'weyland-lab 36' 0 'closed'
  stub_case gh_state 'stud.io 40'     0 'open'
  stub_dispatch port_delete
  run main
  [ "$status" -eq 0 ]
  called_with port_delete '111'
  not_called_with port_delete '222'
}

@test "main: deletes NOTHING when GitHub cannot be reached" {
  lib_source
  seed_entities "$TWO_ENTITIES"
  stub_dispatch gh_state
  stub_case gh_state 'weyland-lab 36' 1 ''
  stub_case gh_state 'stud.io 40'     1 ''
  stub_dispatch port_delete
  run main
  # Non-zero because the run could not do its job — and, critically, nothing was deleted.
  [ "$status" -ne 0 ]
  never_called port_delete
}

@test "main: one unreachable PR does not stop the others, and does not delete it" {
  lib_source
  seed_entities "$TWO_ENTITIES"
  stub_dispatch gh_state
  stub_case gh_state 'weyland-lab 36' 1 ''
  stub_case gh_state 'stud.io 40'     0 'closed'
  stub_dispatch port_delete
  run main
  [ "$status" -ne 0 ]
  called_with port_delete '222'
  not_called_with port_delete '111'
}

@test "main: DRY RUN reports what it would reap and deletes nothing" {
  lib_source
  seed_entities "$TWO_ENTITIES"
  stub_dispatch gh_state
  stub_case gh_state 'weyland-lab 36' 0 'closed'
  stub_case gh_state 'stud.io 40'     0 'open'
  stub_dispatch port_delete
  PORT_REAP_DRY_RUN=1 run main
  [ "$status" -eq 0 ]
  never_called port_delete
  [[ "$output" == *"would reap"* ]]
}

@test "main: an entity with no prNumber is skipped, not guessed at" {
  lib_source
  seed_entities '{"entities":[{"identifier":"333","properties":{"status":"open"},"relations":{"repository":"weyland-lab"}}]}'
  stub_dispatch gh_state
  stub_dispatch port_delete
  run main
  [ "$status" -ne 0 ]
  never_called port_delete
  [[ "$output" == *"333"* ]]
}

@test "main: an entity with no repository relation is skipped, not guessed at" {
  lib_source
  seed_entities '{"entities":[{"identifier":"444","properties":{"prNumber":9,"status":"open"},"relations":{}}]}'
  stub_dispatch gh_state
  stub_dispatch port_delete
  run main
  [ "$status" -ne 0 ]
  never_called port_delete
  [[ "$output" == *"444"* ]]
}

@test "main: a genuinely EMPTY entity list is a clean no-op, and SAYS which it was" {
  # Deliberately NOT fatal — every open PR being merged is a legitimate state. What must never happen
  # is an empty list that came from a broken fetch reading the same as a real one, so the fetch fails
  # closed separately (above) and this path announces itself explicitly in the job log.
  lib_source
  seed_entities '{"entities":[]}'
  stub_dispatch port_delete
  run main
  [ "$status" -eq 0 ]
  never_called port_delete
  [[ "$output" == *"0 open PR entit"* ]]
}

@test "main: refuses to run at all without Port credentials" {
  lib_source
  seed_entities "$TWO_ENTITIES"
  stub_dispatch port_delete
  unset PORT_CLIENT_ID
  run main
  [ "$status" -ne 0 ]
  never_called port_delete
  [[ "$output" == *"PORT_CLIENT_ID"* ]]
}

@test "main: refuses to run at all without a GitHub token" {
  lib_source
  seed_entities "$TWO_ENTITIES"
  stub_dispatch port_delete
  unset GITHUB_TOKEN
  run main
  [ "$status" -ne 0 ]
  never_called port_delete
  [[ "$output" == *"GITHUB_TOKEN"* ]]
}

@test "main: reports the reap count so a run that did nothing is distinguishable from one that could not" {
  lib_source
  seed_entities "$TWO_ENTITIES"
  stub_dispatch gh_state
  stub_case gh_state 'weyland-lab 36' 0 'closed'
  stub_case gh_state 'stud.io 40'     0 'open'
  stub_dispatch port_delete
  run main
  [ "$status" -eq 0 ]
  [[ "$output" == *"2 open PR entit"* ]]
  [[ "$output" == *"1 reaped"* ]]
}
