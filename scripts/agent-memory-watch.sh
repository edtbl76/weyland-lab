#!/usr/bin/env bash
# agent-memory-watch.sh — the shared agent memory's watchdog (B182, 2026-10-03). Run every 15 min by the user timer
# nodes/rogueone/systemd/agent-memory-watch.{service,timer}.
#
#   1. secrets — gitleaks over the notes (~/agent-memory). Basic Memory ACCEPTS a token-shaped note (verified
#      2026-10-03), so this is where one gets FLAGGED. Findings are redacted; a value is never printed.
#   2. health  — scripts/check-shared-memory.py --read-only: the store answers and its index holds every note.
#
# The verdict goes to an Uptime-Kuma PUSH monitor (KUMA_MEMORY_PUSH_URL in scripts/.env) — a dead-man's switch, so a
# watcher that stops running alerts too (same mechanism as restic-backup / machine-inv-drift).
# EXIT: 0 clean + healthy · 1 a finding (secret, incomplete index) · 2 could not check (scanner failed, store
# unreachable, no notes dir). Fail closed: an unscanned directory or an unanswered store is never "clean".
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "${AGENT_MEMORY_NO_ENV:-}" ] && [ -f "$REPO_ROOT/scripts/.env" ]; then
  set -a; . "$REPO_ROOT/scripts/.env"; set +a
fi
MEM_DIR="${AGENT_MEMORY_DIR:-$HOME/agent-memory}"
GITLEAKS_IMAGE="${GITLEAKS_IMAGE:-zricethezav/gitleaks:v8.21.2}"   # same version the scan suite pins
CHECK_CMD="${CHECK_CMD:-$HOME/.local/bin/uv run -q --with mcp python $REPO_ROOT/scripts/check-shared-memory.py --read-only}"

verdict=0; notes=()
worst() { [ "$1" -gt "$verdict" ] && verdict="$1"; return 0; }

if [ ! -d "$MEM_DIR" ]; then
  notes+=("notes dir $MEM_DIR missing"); worst 2
else
  out="$(docker run --rm --user "$(id -u):$(id -g)" -v "$MEM_DIR:/scan:ro" "$GITLEAKS_IMAGE" \
         dir /scan --no-banner --redact --exit-code 1 2>&1)"; rc=$?
  case "$rc" in
    0) notes+=("no secrets") ;;
    1) n="$(grep -oE 'leaks found: [0-9]+' <<<"$out" | grep -oE '[0-9]+' | head -1)"
       notes+=("secret found in the notes: ${n:-?} finding(s) — run gitleaks (runbook) and remove it"); worst 1 ;;
    *) notes+=("could not scan for secrets (gitleaks exit $rc): $(tail -1 <<<"$out")"); worst 2 ;;
  esac
fi

hout="$($CHECK_CMD 2>&1)"; hrc=$?
case "$hrc" in
  0) notes+=("store healthy") ;;
  1) notes+=("store answers but a check failed: $(grep -m1 -E 'FAIL' <<<"$hout")"); worst 1 ;;
  *) notes+=("store unreachable: $(tail -1 <<<"$hout" | cut -c1-160)"); worst 2 ;;
esac

msg="$(printf '%s; ' "${notes[@]}")"; msg="${msg%; }"
echo "agent-memory-watch: exit $verdict — $msg"

if [ -z "${KUMA_MEMORY_PUSH_URL:-}" ]; then
  echo "KUMA_MEMORY_PUSH_URL unset — verdict NOT reported to Kuma (runbook § Watchdog)" >&2
else
  state=up; [ "$verdict" -ne 0 ] && state=down
  q="$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$msg")"
  curl -fsS -m 15 "${KUMA_MEMORY_PUSH_URL}?status=${state}&msg=${q}" >/dev/null 2>&1 \
    || echo "could not reach Kuma — the push monitor will alert on the missed heartbeat" >&2
fi
exit "$verdict"
