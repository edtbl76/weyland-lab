#!/usr/bin/env bash
# whisper-stability-check.sh — is whisper's transcript the SAME, and right, every time? (2026-11-19)
#
# Sends the JFK clip to whisper's native /inference RUNS times (temperature 0, so the decode should be deterministic)
# and passes only if every run has the known words. Case, commas, full stops and segment line breaks are ignored;
# any word difference, or an empty transcript, fails. Found 2026-11-19: timberback's GPU whisper decoded the same
# request differently run to run (8 calls, 4 transcripts, one saying "do not ask"), while the same build on CPU gave
# 12/12 identical. Runbook: docs/runbooks/transcription-whisper.md § Stability check.
#
# usage: whisper-stability-check.sh [URL] [RUNS]
#   URL   default http://192.168.1.233:30881/inference (the whisper-lan NodePort, native path)
#   RUNS  default 10
# exit: 0 stable (every run right) · 1 UNSTABLE (some run differs or is empty) · 2 usage error or UNKNOWN (a call failed)
set -uo pipefail

URL="${1:-http://192.168.1.233:30881/inference}"
RUNS="${2:-10}"
HERE="$(cd "$(dirname "$0")" && pwd)"
AUDIO="${WHISPER_CHECK_AUDIO:-$HERE/../nodes/mother/lab/weyland-platform/services/whisper-cuda/jfk.wav}"
WANT="and so my fellow americans ask not what your country can do for you ask what you can do for your country"

if ! [[ "$RUNS" =~ ^[1-9][0-9]*$ ]]; then
  echo "usage: $0 [URL] [RUNS]  (RUNS a positive whole number, got '$RUNS')"; exit 2
fi

# lower-case, drop commas and full stops, turn line breaks into spaces, squeeze and trim spaces
normalise() { tr '\n' ' ' | tr '[:upper:]' '[:lower:]' | tr -d '.,' | tr -s ' ' | sed 's/^ //; s/ $//'; }

declare -A seen=()
order=()
right=0
for ((i = 1; i <= RUNS; i++)); do
  if ! raw="$(curl -sS -m 120 "$URL" -F "file=@$AUDIO" -F response_format=text -F temperature=0.0 2>&1)"; then
    echo "UNKNOWN: call $i of $RUNS to $URL failed: ${raw:0:200}"; exit 2
  fi
  text="$(printf '%s' "$raw" | normalise)"
  [ "$text" = "$WANT" ] && right=$((right + 1))
  key="${text:-(empty)}"
  [ -n "${seen[$key]+x}" ] || order+=("$key")
  seen[$key]=$(( ${seen[$key]:-0} + 1 ))
done

for key in "${order[@]}"; do
  if [ "$key" = "$WANT" ]; then mark="right"; else mark="WRONG"; fi
  printf '  %3d x %-5s %s\n' "${seen[$key]}" "$mark" "$key"
done
if [ "$right" -eq "$RUNS" ]; then
  echo "stable: $RUNS/$RUNS runs have the known words ($URL)"; exit 0
fi
echo "UNSTABLE: $right/$RUNS runs have the known words ($URL)"; exit 1
