#!/usr/bin/env bats
# B234 — the private lane's guarantee: a wl-private-* alias reaches ONLY self-hosted Ollama on an allowlisted LAN host,
# and when that host is down the call fails instead of falling back to a hosted provider. Every way LiteLLM could send a
# private alias somewhere else is a case here: a hosted target, an off-allowlist host, a hosted fallback, a router-wide
# fallback, a wildcard or group alias that captures the name. Fails closed: no private alias, or a config it cannot
# read, is a broken guard (exit 2), not a pass.

setup() {
  CHECK="${BATS_TEST_DIRNAME}/../check-private-lanes.py"
  CONFIG="${BATS_TEST_DIRNAME}/../../nodes/mother/lab/weyland-platform/k8s/litellm/configmap.yaml"
  FX="${BATS_TEST_DIRNAME}/fixtures/private-lanes"
}

@test "the live LiteLLM config keeps every private lane private" {
  run python3 "$CHECK" "$CONFIG"
  [ "$status" -eq 0 ] && [[ "$output" == OK* ]] || { echo "status=$status $output"; return 1; }
}

@test "local targets and a private-to-private fallback pass" {
  run python3 "$CHECK" "$FX/ok.yaml"
  [ "$status" -eq 0 ] && [[ "$output" == *"2 private alias(es)"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a private alias pointed at a hosted provider is caught" {
  run python3 "$CHECK" "$FX/hosted-target.yaml"
  [ "$status" -eq 1 ] && [[ "$output" == *"wl-private-rag"*"not self-hosted Ollama"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a second deployment on a host outside the allowlist is caught" {
  run python3 "$CHECK" "$FX/off-allowlist.yaml"
  [ "$status" -eq 1 ] && [[ "$output" == *"ollama.example.com"*"not on the LAN allowlist"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a fallback from a private alias to a hosted one is caught" {
  run python3 "$CHECK" "$FX/hosted-fallback.yaml"
  [ "$status" -eq 1 ] && [[ "$output" == *"fallbacks: wl-private-rag -> wl-default"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a router-wide default fallback is caught (it applies to private aliases too)" {
  run python3 "$CHECK" "$FX/default-fallbacks.yaml"
  [ "$status" -eq 1 ] && [[ "$output" == *"default_fallbacks"*"gemini-flash"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a context-window fallback in litellm_settings is caught" {
  run python3 "$CHECK" "$FX/context-window.yaml"
  [ "$status" -eq 1 ] && [[ "$output" == *"context_window_fallbacks: wl-private-rag -> gemini-flash"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a wildcard route that captures private names is caught" {
  run python3 "$CHECK" "$FX/wildcard.yaml"
  [ "$status" -eq 1 ] && [[ "$output" == *"wildcard 'wl-*' captures private names"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a group alias that maps a private name elsewhere is caught" {
  run python3 "$CHECK" "$FX/group-alias.yaml"
  [ "$status" -eq 1 ] && [[ "$output" == *"model_group_alias: wl-private-chat -> wl-default"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a config with no private alias is a broken guard, not a pass" {
  run python3 "$CHECK" "$FX/none.yaml"
  [ "$status" -eq 2 ] && [[ "$output" == *"no wl-private-* alias"* ]] || { echo "status=$status $output"; return 1; }
}

@test "a config it cannot read is a broken guard, not a pass" {
  run python3 "$CHECK" "$BATS_TEST_DIRNAME/no-such-file.yaml"
  [ "$status" -eq 2 ] && [[ "$output" == *"cannot read"* ]] || { echo "status=$status $output"; return 1; }
}
