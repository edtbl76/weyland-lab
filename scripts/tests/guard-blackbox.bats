#!/usr/bin/env bats
#
# scripts/integration/guard-blackbox.sh — BLACK-BOX integration test of the LIVE weyland-guard (B88 #2).
#
# WHAT THIS IS. The repo had NO test tier above unit: nothing asserted that a request actually crosses
# into a running service and comes back correct. `app.py` (the guard's HTTP layer) sat at 0% because it
# is un-importable in the unit lane (needs fastapi/httpx), and its routes — validation → pipeline →
# verdict → response-model → auth — were never exercised end to end. This lane closes that by hitting the
# DEPLOYED guard over HTTP with real payloads and asserting real verdicts: the actual artifact, with
# Postgres and the baked validators wired together. The mesh is PERMISSIVE and the guard carries no
# AuthorizationPolicy, so an in-cluster caller reaches :8080 in plaintext (verified against the manifests).
#
# THE ONE DISCIPLINE THAT MATTERS. Three outcomes, NEVER conflated:
#   0  every assertion passed
#   1  the guard is REACHABLE but MISBEHAVED (wrong verdict, empty validators, error status) -> real defect
#   2  the guard could not be reached, or the lane could not run (transport failure, missing tool) -> broken lane
# A connection failure that read as "pass" would be the exact absence-as-success this repo keeps naming —
# a green lane proving nothing because the thing under test was never contacted. So transport failure fails
# CLOSED to 2, and a non-2xx that HTTP actually returned is a real finding (1), never a 2 and never a pass.

load helper

BB="scripts/integration/guard-blackbox.sh"

setup() {
  setup_stubs
  # The curl test-double reads a per-path response spec from $CURL_DIR: line 1 = curl exit code
  # (0 ok, non-zero = transport failure), line 2 = HTTP status, lines 3+ = response body.
  CURL_DIR="$STUB_DIR/curlresp"
  mkdir -p "$CURL_DIR"
  export CURL_DIR
  cat >"$STUB_DIR/curl" <<'CURL'
#!/usr/bin/env bash
# test double for curl: honours -o <file> and -w, treats the last non-flag arg as the URL.
out=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -w|-X|-H|-d|--data|--data-raw|--max-time) shift 2 ;;
    -sS|-s|-S|-f|-k) shift ;;
    --*) shift ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
rest="${url#*://}"; path="/${rest#*/}"
key="$(printf '%s' "$path" | tr '/' '_')"
spec="$CURL_DIR/$key"
if [ ! -f "$spec" ]; then printf '000'; exit 7; fi      # unknown path -> transport-style failure
rc="$(sed -n 1p "$spec")"; code="$(sed -n 2p "$spec")"; body="$(sed -n '3,$p' "$spec")"
[ -n "$out" ] && printf '%s' "$body" >"$out"
printf '%s' "$code"
exit "$rc"
CURL
  chmod +x "$STUB_DIR/curl"
  export GUARD_BASE_URL="http://guard.test:8080"
}

teardown() { teardown_stubs; return 0; }

# curl_resp <path> <curl-rc> <http-code> <body> — register one canned response.
curl_resp() {
  local key; key="$(printf '%s' "$1" | tr '/' '_')"
  { printf '%s\n%s\n%s' "$2" "$3" "$4"; } >"$CURL_DIR/$key"
}

# The healthy fixture: every endpoint answers the way a correctly-running guard does.
healthy_guard() {
  curl_resp /health      0 200 '{"status":"ok","validators":["policy.gate","prompt_guard.injection","pii.presidio"]}'
  curl_resp /ready       0 200 '{"status":"ready","validators":["policy.gate"]}'
  curl_resp /guard/output 0 200 '{"request_id":"bb","decision":"allow"}'
  # The live guard ships every model validator in SHADOW; only policy.gate enforces. So a hostile
  # input returns `allow` in prod (the injection scorer records but does not block). The input
  # assertion is a CONTRACT check (valid decision), not a verdict check, so `allow` here is healthy.
  curl_resp /guard/input 0 200 '{"request_id":"bb","decision":"allow","verdict":null}'
  curl_resp /guard/act   0 200 '{"request_id":"bb","decision":"block","verdict":{"validator":"policy.gate","decision":"block","reason":"no actor"}}'
}

@test "a fully-healthy guard passes with exit 0" {
  healthy_guard
  run bash "$BB"
  [ "$status" -eq 0 ]
}

@test "guard UNREACHABLE (transport failure on /health) is a BROKEN lane (2), never a pass" {
  # curl exit 7 = could not connect. This must fail CLOSED — verifying nothing is not verifying success.
  curl_resp /health 7 000 ''
  run bash "$BB"
  [ "$status" -eq 2 ]
  [[ "$output" == *"reach"* || "$output" == *"unreachable"* || "$output" == *"cannot run"* ]]
}

@test "a NON-2xx that HTTP actually returned is a REAL defect (1), not a broken-lane 2" {
  # The distinction that matters: the guard answered (transport fine), it answered WRONG. That is the
  # estate misbehaving, not the lane failing — same split the test lanes draw between 1 and 2.
  healthy_guard
  curl_resp /health 0 500 '{"detail":"internal error"}'
  run bash "$BB"
  [ "$status" -eq 1 ]
}

@test "an EMPTY validator set is a real regression (1) — models silently failed to load" {
  # /health returns 200 the moment PID 1 is alive even with zero validators loaded (the app answers
  # 'allow' to everything). A green /health with no validators is a guard that enforces NOTHING — the
  # readiness-without-a-probe class from project.md, so it must fail.
  healthy_guard
  curl_resp /health 0 200 '{"status":"ok","validators":[]}'
  run bash "$BB"
  [ "$status" -eq 1 ]
  [[ "$output" == *"validator"* ]]
}

@test "the INPUT hook is asserted by CONTRACT, not verdict — 'allow' passes (guard ships SHADOW)" {
  # The guard runs its model validators in SHADOW by design, so a hostile input returns allow in prod.
  # Asserting block would be wrong today; the input assertion only requires a VALID decision back.
  healthy_guard   # healthy_guard already sets /guard/input -> allow
  run bash "$BB"
  [ "$status" -eq 0 ]
}

@test "the INPUT hook contract also accepts 'block' — mode-agnostic (survives a promote to enforce)" {
  # If prompt_guard is later correctly promoted to block mode, the same input returns block. The test
  # must NOT fight that — a valid decision either way is a pass.
  healthy_guard
  curl_resp /guard/input 0 200 '{"request_id":"bb","decision":"block","verdict":{"validator":"prompt_guard.injection"}}'
  run bash "$BB"
  [ "$status" -eq 0 ]
}

@test "the INPUT hook returning NO valid decision is a real defect (1) — route/pipeline broken" {
  healthy_guard
  curl_resp /guard/input 0 200 '{"request_id":"bb","decision":"maybe"}'
  run bash "$BB"
  [ "$status" -eq 1 ]
  [[ "$output" == *"input"* ]]
}

@test "an actor-less ACT that is ALLOWED is a real regression (1) — policy.gate not enforcing" {
  healthy_guard
  curl_resp /guard/act 0 200 '{"request_id":"bb","decision":"allow"}'
  run bash "$BB"
  [ "$status" -eq 1 ]
}

@test "a benign OUTPUT that is BLOCKED is a real defect (1) — the guard is over-blocking" {
  healthy_guard
  curl_resp /guard/output 0 200 '{"request_id":"bb","decision":"block","verdict":{"validator":"grounding.nli"}}'
  run bash "$BB"
  [ "$status" -eq 1 ]
}

@test "a 200 with an UNPARSEABLE body is a real defect (1) — the guard returned garbage" {
  healthy_guard
  curl_resp /ready 0 200 'this is not json'
  run bash "$BB"
  [ "$status" -eq 1 ]
}

@test "GUARD_BASE_URL is honoured (the URL the script builds reaches the double)" {
  # Proven implicitly by every other test using guard.test, but assert the override plumbing directly:
  # an unset-path base still resolves /health from the spec dir.
  healthy_guard
  GUARD_BASE_URL="http://elsewhere.test:9999" run bash "$BB"
  [ "$status" -eq 0 ]
}
