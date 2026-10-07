#!/usr/bin/env bash
set -euo pipefail
#
# clef-flash — start/stop the on-demand Clef-flash decision server (B174) on the rogueone GPU.
#
# Cloudflare's Apache-2.0 decision model behind the Jev / SystemOne API (POST /v1/systemone on :8004). The operator's
# decision-model shadow uses it when OPERATOR_DECIDE_URL points here (default is TypeSafe's hosted Jev).
#
# It holds ~8.5 GB of the 16 GB card, so it does NOT fit beside the operator's qwen2.5:7b-operator (6.6 GB) and the
# desktop (~4.5 GB). `start` unloads qwen first; while Clef is up, Ollama reloads qwen partly on CPU and live operator
# calls can hit their 60 s timeout. `stop` frees the card and reloads qwen, then CHECKS it is fully on the GPU — the
# 2026-10-07 benchmark left it 0.88 of 6.8 GB on the card until reloaded. Keep the window short.
#
# Docs: docs/runbooks/decision-models.md · docs/concepts/decision-models.md
#
# Usage: scripts/clef-flash.sh {start|stop|status|logs|smoke}
# Exit: 0 ok · 1 not serving / smoke failed / qwen not back on the GPU · 2 usage

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="${CLEF_COMPOSE:-$SCRIPT_DIR/../nodes/rogueone/services/gpu-inference/docker-compose.yml}"
CLEF_URL="${CLEF_URL:-http://localhost:8004}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
OPERATOR_MODEL="${OPERATOR_MODEL:-qwen2.5:7b-operator}"
export DOCKER_HOST="${DOCKER_HOST_OVERRIDE:-unix:///var/run/docker.sock}"   # native engine (nvidia runtime)
DC=(docker compose -f "$COMPOSE")

usage() {
  cat <<'HELP'
clef-flash — on-demand Clef-flash decision server (B174), Jev-compatible, on :8004. Run on rogueone.

  start   unload the operator's qwen, build + start Clef-flash (first start downloads ~19 GB of weights)
  stop    stop Clef-flash, reload qwen, and check it is fully back on the GPU (exit 1 if not)
  status  container state + /health
  logs    follow the server log (Ctrl+C to detach)
  smoke   one real decision through POST /v1/systemone — exit 1 unless it returns a choice
HELP
}

unload_operator_model() {
  curl -s -o /dev/null --max-time 30 "$OLLAMA_URL/api/generate" -d "{\"model\":\"$OPERATOR_MODEL\",\"keep_alive\":0}" || true
}

# Reload qwen and print "<size_vram> <size>" of the loaded model (empty if it is not loaded).
reload_operator_model() {
  unload_operator_model
  curl -s -o /dev/null --max-time 180 "$OLLAMA_URL/api/generate" \
    -d "{\"model\":\"$OPERATOR_MODEL\",\"prompt\":\"ok\",\"stream\":false,\"options\":{\"num_predict\":1}}" || true
  curl -s --max-time 10 "$OLLAMA_URL/api/ps" \
    | jq -r --arg m "$OPERATOR_MODEL" '.models[]? | select(.name == $m) | "\(.size_vram) \(.size)"' 2>/dev/null || true
}

smoke() {
  local reply choice
  reply="$(curl -s --max-time 120 "$CLEF_URL/v1/systemone" -H 'Content-Type: application/json' -d '{
    "model": "clef-flash",
    "state": "Our checkout started returning errors and orders are blocked.",
    "questions": {"team": {"type": "choice", "instructions": "Which team should handle the message?",
                           "criteria": {"billing": "Payments or invoices", "technical": "Bugs or outages"}}}}')" || reply=""
  choice="$(printf '%s' "$reply" | jq -r '.answers.team.choice // empty' 2>/dev/null || true)"
  if [ -z "$choice" ]; then
    echo "SMOKE FAILED — no choice in the reply: ${reply:-<no reply>}" >&2
    return 1
  fi
  echo "team -> $choice (confidence $(printf '%s' "$reply" | jq -r '.answers.team.confidence'))"
}

case "${1:-}" in
  start)
    unload_operator_model
    "${DC[@]}" up -d --build clef-flash
    echo "starting Clef-flash — ready when: $0 status shows /health ok. Run '$0 stop' when done (it reloads qwen)."
    ;;
  stop)
    "${DC[@]}" rm -sf clef-flash
    read -r vram size <<<"$(reload_operator_model)" || true
    if [ -z "${size:-}" ] || [ "${vram:-0}" != "$size" ]; then
      echo "Clef-flash stopped, but $OPERATOR_MODEL is NOT fully on the GPU (vram=${vram:-none} of ${size:-none})." >&2
      echo "Free the card (nvidia-smi), then re-run: $0 stop" >&2
      exit 1
    fi
    echo "Clef-flash stopped; $OPERATOR_MODEL back fully on the GPU ($vram bytes)."
    ;;
  status)
    "${DC[@]}" ps clef-flash
    echo "--- /health ---"
    curl -sf --max-time 5 "$CLEF_URL/health" || { echo "not serving (loading, or run: $0 start)"; exit 1; }
    echo
    ;;
  logs)
    "${DC[@]}" logs -f clef-flash
    ;;
  smoke)
    curl -sf --max-time 5 "$CLEF_URL/health" >/dev/null 2>&1 || { echo "Clef-flash not serving — run: $0 start" >&2; exit 1; }
    smoke
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
