#!/usr/bin/env bats
#
# new-service.sh — scaffolds a real service FROM a golden path (B153). It makes decisions (validate
# the name/path, rewrite the golden token, drop the lane's selfcheck probe), so it is tested like any
# other decision-making shell. Fail-closed cases assert the REASON, not just a non-zero status.

load helper

setup() {
  NS="$REPO_ROOT/scripts/new-service.sh"
  DEST_ROOT="$(mktemp -d)"
}

teardown() {
  [ -n "${DEST_ROOT:-}" ] && [ -d "$DEST_ROOT" ] && rm -rf "$DEST_ROOT"
  return 0
}

@test "a non-kebab service name is refused with a reason" {
  run bash "$NS" python/fastapi Bad_Name "$DEST_ROOT/x"
  [ "$status" -eq 2 ]
  [[ "$output" == *"kebab-case"* || "$output" == *"lowercase"* ]]
}

@test "a missing golden path is refused with a reason" {
  run bash "$NS" python/does-not-exist svc "$DEST_ROOT/y"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no golden path"* ]]
}

@test "an existing destination is refused (never overwritten)" {
  mkdir -p "$DEST_ROOT/taken"
  run bash "$NS" python/fastapi svc "$DEST_ROOT/taken"
  [ "$status" -eq 2 ]
  [[ "$output" == *"already exists"* ]]
}

@test "scaffolding rewrites the golden token and drops the selfcheck probe" {
  run bash "$NS" python/fastapi billing-api "$DEST_ROOT/billing"
  [ "$status" -eq 0 ]
  [ -f "$DEST_ROOT/billing/main.py" ]
  # SERVICE_NAME rewritten to the new name; no golden- token survives anywhere.
  grep -q 'SERVICE_NAME = "billing-api"' "$DEST_ROOT/billing/main.py"
  ! grep -rq 'golden-python-fastapi' "$DEST_ROOT/billing"
  # the lane's deliberately-failing probe must NOT ship in a real service.
  [ ! -d "$DEST_ROOT/billing/selfcheck" ]
  # a service README replaced the golden-path one.
  grep -q "Scaffolded from" "$DEST_ROOT/billing/README.md"
}

@test "the printed onboarding declaration names the new service" {
  run bash "$NS" node/express orders "$DEST_ROOT/orders"
  [ "$status" -eq 0 ]
  [[ "$output" == *"key: orders"* ]]
  [[ "$output" == *"port_component: orders"* ]]
}
