#!/usr/bin/env bats
# B174 — scripts/clef-flash.sh, the on-demand Clef-flash decision server on the rogueone GPU.
#
# The script's decisions are what these test: smoke passes ONLY on a real `choice` in the reply (a reply without one,
# an error body, or no server is exit 1 — never a pass), and `stop` passes only when the operator's qwen is back FULLY
# on the GPU (the 2026-10-07 benchmark left it 0.88 of 6.8 GB on the card, failing live operator calls). `docker` and
# `curl` are stubs; `curl` answers by URL from env so each test sets exactly the state it asserts on.

setup() {
  load helper
  setup_stubs
  SCRIPT="$REPO_ROOT/scripts/clef-flash.sh"
  stub docker 0 ""
  cat >"$STUB_DIR/curl" <<'EOF'
#!/usr/bin/env bash
printf 'curl %s\n' "$*" >> "$STUB_LOG"
case "$*" in
  */health*)      [ "${FAKE_HEALTH:-up}" = up ] && { echo '{"status":"ok"}'; exit 0; } || exit 7 ;;
  */v1/systemone*) printf '%s' "${FAKE_SMOKE:-}"; exit 0 ;;
  */api/ps*)      printf '%s' "${FAKE_PS:-{\"models\":[]\}}"; exit 0 ;;
  *)              exit 0 ;;
esac
EOF
  chmod +x "$STUB_DIR/curl"
}

teardown() {
  teardown_stubs
}

@test "no verb prints usage and exits 2" {
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"start"*"stop"*"smoke"* ]]
}

@test "smoke with no server is exit 1 and says it is not serving" {
  FAKE_HEALTH=down run bash "$SCRIPT" smoke
  [ "$status" -eq 1 ]
  [[ "$output" == *"not serving"* ]]
}

@test "smoke passes on a real choice and prints it" {
  FAKE_SMOKE='{"answers":{"team":{"choice":"technical","confidence":0.93}}}' run bash "$SCRIPT" smoke
  [ "$status" -eq 0 ]
  [[ "$output" == *"team -> technical"* ]]
}

@test "smoke fails on an error body — an answer without a choice is not a pass" {
  FAKE_SMOKE='{"error":"RuntimeError: CUDA out of memory"}' run bash "$SCRIPT" smoke
  [ "$status" -eq 1 ]
  [[ "$output" == *"SMOKE FAILED"*"CUDA out of memory"* ]]
}

@test "smoke fails on an empty reply" {
  FAKE_SMOKE='' run bash "$SCRIPT" smoke
  [ "$status" -eq 1 ]
  [[ "$output" == *"SMOKE FAILED"*"<no reply>"* ]]
}

@test "stop passes when qwen is back fully on the GPU" {
  FAKE_PS='{"models":[{"name":"qwen2.5:7b-operator","size_vram":6593561230,"size":6593561230}]}' run bash "$SCRIPT" stop
  [ "$status" -eq 0 ]
  [[ "$output" == *"back fully on the GPU"* ]]
  grep -q "docker compose .* rm -sf clef-flash" "$STUB_LOG"
}

@test "stop fails when qwen came back partly on the CPU" {
  FAKE_PS='{"models":[{"name":"qwen2.5:7b-operator","size_vram":878150942,"size":6825818035}]}' run bash "$SCRIPT" stop
  [ "$status" -eq 1 ]
  [[ "$output" == *"NOT fully on the GPU"*"vram=878150942 of 6825818035"* ]]
}

@test "stop fails when qwen did not load at all" {
  FAKE_PS='{"models":[]}' run bash "$SCRIPT" stop
  [ "$status" -eq 1 ]
  [[ "$output" == *"NOT fully on the GPU"*"vram=none of none"* ]]
}

@test "start unloads the operator's model before starting Clef" {
  run bash "$SCRIPT" start
  [ "$status" -eq 0 ]
  first_unload=$(grep -n 'keep_alive":0' "$STUB_LOG" | head -1 | cut -d: -f1)
  compose_up=$(grep -n "up -d --build clef-flash" "$STUB_LOG" | head -1 | cut -d: -f1)
  [ -n "$first_unload" ] && [ -n "$compose_up" ] && [ "$first_unload" -lt "$compose_up" ]
}
