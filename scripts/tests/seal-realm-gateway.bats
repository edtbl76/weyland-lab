#!/usr/bin/env bats
# B249 (2026-11-19) — nodes/mother/lab/weyland-platform/scripts/seal_realm_gateway.sh seals the two secrets the Realm
# behind Bifrost's Agent Gateway needs, from the gitignored scripts/.env:
#   realm-gateway-token     REALM_GATEWAY_TOKEN  (read by Bifrost, which sends it, and by the Realm, which checks it)
#   weyland-operator-realm  REALM_GATEWAY_VK     (the operator's Bifrost virtual key, from the register script's ensure-vk)
# Fail closed: a missing or empty value stops the run naming it, and seals nothing (a secret sealed without its value
# would silently turn the paid path off, or point the operator at the gateway with no key). Values go through stdin,
# never the command line, and are never printed. kubectl/kubeseal are stubs that record what they were given.

setup() {
  load helper
  SCRIPT="$REPO_ROOT/nodes/mother/lab/weyland-platform/scripts/seal_realm_gateway.sh"
  T="$(mktemp -d)"; mkdir -p "$T/bin" "$T/out"
  cat > "$T/bin/kubectl" <<'SH'
#!/bin/sh
# record args; echo a Secret whose data came from stdin, so the test can see the value went through stdin
printf '%s\n' "$*" >> "$STUB_DIR/kubectl.args"
v="$(cat)"; printf 'kind: Secret\nargs: %s\nstdin: %s\n' "$*" "$v"
SH
  cat > "$T/bin/kubeseal" <<'SH'
#!/bin/sh
printf '%s\n' "$*" >> "$STUB_DIR/kubeseal.args"
sed 's/^stdin: .*/encryptedData: SEALED/'
SH
  chmod +x "$T/bin/kubectl" "$T/bin/kubeseal"
  export PATH="$T/bin:$PATH" STUB_DIR="$T" SEAL_OUT_DIR="$T/out" REALM_ENV_FILE="$T/.env"
}

teardown() { rm -rf "$T"; }

@test "seals both secrets from .env through stdin, prints no value" {
  printf 'REALM_GATEWAY_TOKEN=tok-123\nREALM_GATEWAY_VK=sk-bf-xyz\n' > "$T/.env"
  run bash "$SCRIPT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ -f "$T/out/weyland__realm-gateway-token.yaml" ] && [ -f "$T/out/weyland__weyland-operator-realm.yaml" ]
  grep -q "realm-gateway-token" "$T/kubectl.args" && grep -q "weyland-operator-realm" "$T/kubectl.args"
  grep -q "REALM_GATEWAY_TOKEN=/dev/stdin" "$T/kubectl.args"
  ! grep -q "tok-123\|sk-bf-xyz" "$T/kubectl.args"            # never on a command line
  [[ "$output" != *"tok-123"* && "$output" != *"sk-bf-xyz"* ]]   # never printed
  grep -q "encryptedData: SEALED" "$T/out/weyland__realm-gateway-token.yaml"
}

@test "a missing value stops the run, names it, and seals nothing" {
  printf 'REALM_GATEWAY_TOKEN=tok-123\n' > "$T/.env"
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"REALM_GATEWAY_VK"* ]]
  [ ! -e "$T/out/weyland__realm-gateway-token.yaml" ] && [ ! -e "$T/out/weyland__weyland-operator-realm.yaml" ]
}

@test "an empty value counts as missing" {
  printf 'REALM_GATEWAY_TOKEN=\nREALM_GATEWAY_VK=sk-bf-xyz\n' > "$T/.env"
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"REALM_GATEWAY_TOKEN"* ]]
}

@test "no .env is exit 2, not a seal of nothing" {
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *".env"* ]]
}
