#!/usr/bin/env bats
# Guard for the B137 disease: Port schema that exists ONLY in the UI.
#
# On 2026-08-22 the live org held 51 blueprints / 8 scorecards / 4 integrations while `tofu/port/`
# described 13 / 0 / 0, and `tofu plan` reported no drift the whole time — because plan compares the
# code to the resources TOFU KNOWS ABOUT, and a UI-created blueprint is not one of them. The guard
# asks the inverse question. These tests exist because the guard's own failure mode is the same as
# the bug's: an assertion that silently passes proves nothing, and this repo has now shipped that
# mistake twice INSIDE a guard built to prevent it.
#
# Every case drives the guard through PORT_LIVE_*_JSON + PORT_TF_DIR, so nothing here reaches
# api.port.io. The decision under test is the set comparison, never the network.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-port-iac-coverage.sh"
  WORK="$(mktemp -d)"
  TFDIR="$WORK/tf"
  mkdir -p "$TFDIR"
}

teardown() {
  teardown_stubs
  [ -n "${WORK:-}" ] && [ -d "$WORK" ] && rm -rf "$WORK"
  return 0
}

# --- fixtures ---------------------------------------------------------------------------------
# A miniature org: one hand-authored blueprint (`service`, must be codified), one integration-owned
# one (`githubRepository`, excused because a live integration maps it), one Port system blueprint
# (`_user`, excused by the `_` prefix), and one dormant (`githubUser`, excused by name + reason).

write_live() {
  cat >"$WORK/bp.json" <<'JSON'
{"blueprints":[
  {"identifier":"service","relations":{"github_repository":{"target":"githubRepository"}}},
  {"identifier":"githubRepository","relations":{}},
  {"identifier":"githubUser","relations":{}},
  {"identifier":"_user","relations":{}}
]}
JSON
  cat >"$WORK/sc.json" <<'JSON'
{"scorecards":[{"blueprint":"service","identifier":"production_readiness"}]}
JSON
  cat >"$WORK/ig.json" <<'JSON'
{"integrations":[{"installationId":"github-weyland","config":{"resources":[
  {"kind":"repository","port":{"entity":{"mappings":{"blueprint":"\"githubRepository\""}}}}
]}}]}
JSON
}

write_code() {
  cat >"$TFDIR/main.tf" <<'HCL'
resource "port_blueprint" "service" {
  identifier = "service"
  relations = {
    github_repository = {
      target = "githubRepository"
    }
  }
}

resource "port_scorecard" "service_production_readiness" {
  identifier = "production_readiness"
  blueprint  = "service"
}

resource "port_integration" "github_weyland" {
  installation_id = "github-weyland"
}
HCL
}

guard() {
  PORT_TF_DIR="$TFDIR" \
  PORT_LIVE_BLUEPRINTS_JSON="$WORK/bp.json" \
  PORT_LIVE_SCORECARDS_JSON="$WORK/sc.json" \
  PORT_LIVE_INTEGRATIONS_JSON="$WORK/ig.json" \
    bash "$GUARD" "$@"
}

@test "the guard exists" {
  [ -f "$GUARD" ]
}

# --- the happy path ----------------------------------------------------------------------------

@test "full coverage passes and says so" {
  write_live; write_code
  run guard
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK -- every live blueprint, scorecard and integration"* ]]
}

# --- the three things it must catch --------------------------------------------------------------
# Each of these is a real historical state of this repo, not a hypothetical.

@test "a live blueprint with no code definition FAILS and is named" {
  write_live; write_code
  # `deployment` created in the UI — exactly how the gap opened, one click at a time.
  python3 - "$WORK/bp.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p))
d["blueprints"].append({"identifier":"deployment","relations":{}})
json.dump(d,open(p,"w"))
PY
  run guard
  [ "$status" -ne 0 ]
  # Assert the REASON, not just non-zero: `[ "$status" -ne 0 ]` alone passes on exit 127.
  [[ "$output" == *"live blueprints with NO definition"* ]]
  [[ "$output" == *"deployment"* ]]
}

@test "a live scorecard with no code definition FAILS and is named" {
  write_live; write_code
  python3 - "$WORK/sc.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p))
d["scorecards"].append({"blueprint":"service","identifier":"dora_lead_time"})
json.dump(d,open(p,"w"))
PY
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"live scorecards with NO definition"* ]]
  [[ "$output" == *"service:dora_lead_time"* ]]
}

@test "a live integration with no code definition FAILS and is named" {
  write_live; write_code
  python3 - "$WORK/ig.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p))
d["integrations"].append({"installationId":"weyland-cluster","config":{"resources":[]}})
json.dump(d,open(p,"w"))
PY
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"live integrations with NO definition"* ]]
  [[ "$output" == *"weyland-cluster"* ]]
}

# --- the three excuses, each for its own stated reason ---------------------------------------------

@test "a Port SYSTEM blueprint (_-prefixed) is excused without being listed anywhere" {
  write_live; write_code
  run guard
  [ "$status" -eq 0 ]
  [[ "$output" != *"_user"* ]] || [[ "$output" == *"OK --"* ]]
}

@test "an INTEGRATION-OWNED blueprint is excused because a LIVE integration maps it" {
  write_live; write_code
  run guard
  [ "$status" -eq 0 ]
}

@test "the excuse is DERIVED from the live mapping, not hardcoded: drop the mapping and it FAILS" {
  # The load-bearing property. If `githubRepository` were on a static allow-list, retiring the
  # integration that owns it would leave an orphaned blueprint permanently excused — a dead
  # exception outliving its reason, which is the failure mode this repo hit three times in one day.
  write_live; write_code
  cat >"$WORK/ig.json" <<'JSON'
{"integrations":[{"installationId":"github-weyland","config":{"resources":[
  {"kind":"repository","port":{"entity":{"mappings":{"blueprint":"\"somethingElse\""}}}}
]}}]}
JSON
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"githubRepository"* ]]
}

@test "a DORMANT blueprint is excused only because it is named in the script WITH a reason" {
  write_live; write_code
  # githubUser is in DORMANT_UI_MANAGED. Rename the live one to something not on that list and the
  # guard must object — proving the pass came from the list and not from a blanket github prefix.
  python3 - "$WORK/bp.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p))
for b in d["blueprints"]:
    if b["identifier"] == "githubUser": b["identifier"] = "githubTeam"
json.dump(d,open(p,"w"))
PY
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"githubTeam"* ]]
}

@test "every DORMANT entry carries a reason after the pipe" {
  # The accept-list's whole justification is that it is documented. An entry with an empty reason
  # is an undocumented exception wearing the costume of a documented one.
  run bash -c "PORT_IAC_LIB=1 source '$GUARD'; for e in \"\${DORMANT_UI_MANAGED[@]}\"; do
                 r=\${e#*|}; [ -n \"\$r\" ] && [ \"\$r\" != \"\$e\" ] || { echo \"NO REASON: \$e\"; exit 1; }
               done; echo ok"
  [ "$status" -eq 0 ]
  [[ "$output" == *ok* ]]
}

# --- fail-closed -----------------------------------------------------------------------------------
# An absent or unreadable result must never stand for a passing one.

@test "an EMPTY live blueprint list is an error, not a pass" {
  write_live; write_code
  echo '{"blueprints":[]}' >"$WORK/bp.json"
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"EMPTY"* ]]
}

@test "a live payload missing its top-level key is an error, not a pass" {
  write_live; write_code
  echo '{"ok":true}' >"$WORK/ig.json"
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"EMPTY"* ]]
}

@test "a .tf directory with no .tf files is an error, not zero-coverage-passes" {
  write_live
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"no .tf files"* ]]
}

@test "a resource block with no literal identifier is an error, not a silent skip" {
  write_live; write_code
  cat >>"$TFDIR/main.tf" <<'HCL'

resource "port_blueprint" "computed_thing" {
  title = "no identifier here"
}
HCL
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"no literal identifier"* ]]
}

@test "a codified blueprint that is NOT live is an error — the code and the org disagree" {
  write_live; write_code
  cat >>"$TFDIR/main.tf" <<'HCL'

resource "port_blueprint" "ghost" {
  identifier = "ghost"
}
HCL
  run guard
  [ "$status" -ne 0 ]
  [[ "$output" == *"codified but NOT LIVE"* ]]
  [[ "$output" == *"ghost"* ]]
}

# --- the rebuild-order report ------------------------------------------------------------------------

@test "a codified relation targeting an uncodified blueprint is REPORTED, not failed" {
  # service.github_repository -> githubRepository. Not an error: the integration creates that
  # blueprint on install. But it IS the from-scratch apply order, and an unstated order is one
  # somebody rediscovers during a restore.
  write_live; write_code
  run guard
  [ "$status" -eq 0 ]
  [[ "$output" == *"rebuild order"* ]]
  [[ "$output" == *"service.github_repository -> githubRepository"* ]]
}

# --- nested identifiers must not be mistaken for the resource's own ------------------------------------

# NOTE: no backticks in a @test name. bats expands the name as a shell string, so `identifier`
# ran as a command and printed "identifier: command not found" on every single test in the file.
@test "an identifier nested inside a relations block is not read as the blueprint's own" {
  write_live
  # The nested `identifier` MUST come BEFORE the resource's own, or the test is vacuous: the parser
  # takes the first match and would have been right by accident. The real files are shaped this way
  # too — blueprints.tf opens every resource with `calculation_properties`, not `identifier`.
  # Caught by mutation-testing this file: deleting the parser's depth check left this test green.
  cat >"$TFDIR/main.tf" <<'HCL'
resource "port_blueprint" "service" {
  relations = {
    github_repository = {
      target     = "githubRepository"
      identifier = "DECOY"
    }
  }
  identifier = "service"
}

resource "port_scorecard" "service_production_readiness" {
  identifier = "production_readiness"
  blueprint  = "service"
}

resource "port_integration" "github_weyland" {
  installation_id = "github-weyland"
}
HCL
  run guard
  [ "$status" -eq 0 ]
  [[ "$output" != *"DECOY"* ]]
}

# --- --list is read-only -------------------------------------------------------------------------------

@test "--list prints the documented decision and exits 0 even when coverage is incomplete" {
  write_live; write_code
  python3 - "$WORK/bp.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p))
d["blueprints"].append({"identifier":"deployment","relations":{}})
json.dump(d,open(p,"w"))
PY
  run guard --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"Deliberately UI-managed"* ]]
  [[ "$output" == *"Integration-owned"* ]]
}
