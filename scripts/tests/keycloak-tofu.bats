#!/usr/bin/env bats
# B256 (2026-11-23) — scripts/keycloak-tofu.sh reconciles the Keycloak realm with every credential loaded into the env
# and none printed. Decisions under test: a bad mode is usage (exit 2); a missing MinIO key or an unreadable admin
# password stops before tofu runs, naming what is missing (fail closed); otherwise tofu runs in tofu/keycloak with the
# mode, and the admin password reaches it only through the environment. kubectl and tofu are stubs.

setup() {
  load helper
  SCRIPT="$REPO_ROOT/scripts/keycloak-tofu.sh"
  T="$(mktemp -d)"; mkdir -p "$T/bin"
  printf 'AWS_ACCESS_KEY_ID=k\nAWS_SECRET_ACCESS_KEY=s\n' > "$T/env"
  cat > "$T/bin/kubectl" <<'SH'
#!/bin/sh
[ -n "$STUB_NO_SECRET" ] && exit 0
printf '%s' "$(printf 'hunter2' | base64)"
SH
  cat > "$T/bin/tofu" <<'SH'
#!/bin/sh
echo "tofu $* admin=${TF_VAR_kc_admin_password} op=${TF_VAR_operator_password} aws=${AWS_ACCESS_KEY_ID}" > "$STUB_DIR/tofu.args"
SH
  chmod +x "$T/bin/kubectl" "$T/bin/tofu"
  export PATH="$T/bin:$PATH" STUB_DIR="$T" KEYCLOAK_TOFU_ENV="$T/env"
}

teardown() { rm -rf "$T"; }

@test "an unknown mode is usage, exit 2, and tofu never runs" {
  run bash "$SCRIPT" destroy
  [ "$status" -eq 2 ] && [[ "$output" == *usage* ]] && [ ! -f "$T/tofu.args" ]
}

@test "a missing MinIO key stops before tofu, naming it" {
  : > "$T/env"
  run bash "$SCRIPT" plan
  [ "$status" -eq 2 ] && [[ "$output" == *"AWS_ACCESS_KEY_ID"* ]] && [ ! -f "$T/tofu.args" ]
}

@test "an unreadable admin password stops before tofu, naming it" {
  STUB_NO_SECRET=1 run bash "$SCRIPT" plan
  [ "$status" -eq 2 ] && [[ "$output" == *"admin password"* ]] && [ ! -f "$T/tofu.args" ]
}

@test "plan runs tofu in tofu/keycloak with the credentials in the env and prints none of them" {
  run bash "$SCRIPT" plan
  [ "$status" -eq 0 ]
  grep -q -- "-chdir=$REPO_ROOT/nodes/mother/lab/weyland-platform/tofu/keycloak plan" "$T/tofu.args"
  grep -q "admin=hunter2 op=hunter2 aws=k" "$T/tofu.args"
  [[ "$output" != *hunter2* ]]
}
