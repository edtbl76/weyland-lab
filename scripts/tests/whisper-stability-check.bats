#!/usr/bin/env bats
# scripts/whisper-stability-check.sh (2026-11-19) — transcribes the JFK clip N times and passes only if EVERY run has
# the known words. Found 2026-11-19: timberback's GPU whisper decoded the same request differently run to run (8 calls,
# 4 transcripts, one saying "do not ask"), while the same build on CPU gave 12/12 identical. These pin the decisions
# with a stub curl whose replies come one per line from $STUB_REPLIES; the real runs are in the runbook.

setup() {
  T="$BATS_TEST_TMPDIR"; mkdir -p "$T/bin"
  SCRIPT="$BATS_TEST_DIRNAME/../whisper-stability-check.sh"
  cat > "$T/bin/curl" <<'SH'
#!/bin/sh
[ -n "${STUB_CURL_FAIL:-}" ] && { echo "curl: (7) Failed to connect" >&2; exit 7; }
n=$(cat "$STUB_DIR/n" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$STUB_DIR/n"
line=$(sed -n "${n}p" "$STUB_REPLIES")
printf '%b' "$line"
SH
  chmod +x "$T/bin/curl"
  export PATH="$T/bin:$PATH" STUB_DIR="$T" STUB_REPLIES="$T/replies"
  GOOD=' And so my fellow Americans, ask not what your country can do for you, ask what you can do for your country.\n'
}

replies() { : > "$STUB_REPLIES"; for r in "$@"; do printf '%s\n' "$r" >> "$STUB_REPLIES"; done; }

@test "every run has the known words: stable, exit 0" {
  replies "$GOOD" "$GOOD" "$GOOD"
  run bash "$SCRIPT" http://stub/inference 3
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"stable: 3/3 runs"* ]]
}

@test "case, commas, full stops and segment line breaks do not count as differences" {
  replies "$GOOD" ' And so, my fellow Americans,\n ask not what your country can do for you,\n Ask what you can do for your country\n'
  run bash "$SCRIPT" http://stub/inference 2
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "one run with different words fails, exit 1, and names the transcript" {
  replies "$GOOD" ' And so my fellow Americans, do not ask what your country can do for you, ask what you can do for your country.\n' "$GOOD"
  run bash "$SCRIPT" http://stub/inference 3
  [ "$status" -eq 1 ]
  [[ "$output" == *"UNSTABLE: 2/3 runs"* ]]
  [[ "$output" == *"do not ask what your country"* ]]
}

@test "an empty transcript is a failure, never a pass" {
  replies "$GOOD" "" "$GOOD"
  run bash "$SCRIPT" http://stub/inference 3
  [ "$status" -eq 1 ]
  [[ "$output" == *"(empty)"* ]]
}

@test "an unreachable server is unknown, exit 2, not a verdict" {
  STUB_CURL_FAIL=1 run bash "$SCRIPT" http://stub/inference 3
  [ "$status" -eq 2 ]
  [[ "$output" == *"UNKNOWN"* ]]
}

@test "a run count that is not a positive whole number is a usage error, exit 2" {
  run bash "$SCRIPT" http://stub/inference zero
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage:"* ]]
  run bash "$SCRIPT" http://stub/inference 0
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage:"* ]]
}
