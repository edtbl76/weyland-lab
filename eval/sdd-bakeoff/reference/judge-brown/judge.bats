#!/usr/bin/env bats
# Black-box judge for the brownfield trial (the private-lane guard). Exit codes only, as the task text states them:
# 0 safe · 1 a private alias can reach something else · 2 cannot check. Never the guard's wording or file layout.
# Run: TRIAL=<trial repo> bats judge.bats

setup() {
  CHECK="$TRIAL/scripts/check-private-lanes.py"
  CONFIG="$TRIAL/nodes/mother/lab/weyland-platform/k8s/litellm/configmap.yaml"
  FX="$BATS_TEST_DIRNAME"
}

# expect <exit-code> <config> — run the guard, require that exit code
expect() {
  # python3 exits 2 for a MISSING script too, which would fake the guard's own "cannot check" (2): require it first.
  [ -f "$CHECK" ] || { echo "no guard at $CHECK"; return 1; }
  run python3 "$CHECK" "$2"
  if [ "$status" -ne "$1" ]; then
    echo "want exit $1, got $status: $output"
    return 1
  fi
}

@test "the real configmap passes (exit 0)" {
  expect 0 "$CONFIG"
}

@test "the real configmap has both private aliases" {
  python3 -c 'import sys,yaml; c=yaml.safe_load(yaml.safe_load(open(sys.argv[1]))["data"]["config.yaml"]); n={m["model_name"] for m in c["model_list"]}; sys.exit(0 if {"wl-private-rag","wl-private-reason"} <= n else 1)' "$CONFIG"
}

@test "local targets + a private-to-private fallback pass (0)" {
  expect 0 "$FX/ok.yaml"
}

@test "hosted target is caught (1)" {
  expect 1 "$FX/hosted-target.yaml"
}

@test "off-allowlist host is caught (1)" {
  expect 1 "$FX/off-allowlist.yaml"
}

@test "hosted fallback is caught (1)" {
  expect 1 "$FX/hosted-fallback.yaml"
}

@test "router-wide default_fallbacks is caught (1)" {
  expect 1 "$FX/default-fallbacks.yaml"
}

@test "context-window fallback is caught (1)" {
  expect 1 "$FX/context-window.yaml"
}

@test "wildcard capturing private names is caught (1)" {
  expect 1 "$FX/wildcard.yaml"
}

@test "group alias mapping a private name is caught (1)" {
  expect 1 "$FX/group-alias.yaml"
}

@test "no private alias is exit 2" {
  expect 2 "$FX/none.yaml"
}

@test "unreadable file is exit 2" {
  expect 2 "$FX/no-such-file.yaml"
}

# CI wiring: the guard named in .woodpecker.yml, or a bats file under scripts/tests/ that calls it (CI runs `bats scripts/tests/`).
@test "the guard runs in CI" {
  if grep -q "check-private-lanes.py" "$TRIAL/.woodpecker.yml"; then
    return 0
  fi
  grep -rlq "check-private-lanes.py" "$TRIAL/scripts/tests" --include='*.bats'
  grep -q "bats scripts/tests/" "$TRIAL/.woodpecker.yml"
}
