#!/usr/bin/env bash
set -euo pipefail
#
# vllm-bench — start/stop the on-demand vLLM GPU inference bench (B111).
#
# Replaces the old ~/weyland/vllm/start-vllm-qwen + gpu-docker pair, and lives in the repo so it's committed/portable.
# It drives the committed compose (nodes/rogueone/services/gpu-inference/docker-compose.yml) and FORCES the native
# Docker engine socket — rogueone's default context is Docker Desktop, which is a VM with NO GPU. Run ON rogueone.
#
# Docs: docs/runbooks/gpu-inference.md · docs/demos/gpu-inference.md
#
# Usage: scripts/vllm-bench.sh {start|stop|status|logs|smoke}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$SCRIPT_DIR/../nodes/rogueone/services/gpu-inference/docker-compose.yml"   # repo-root scripts → nodes/rogueone/…
export DOCKER_HOST="unix:///var/run/docker.sock"    # native engine (has the nvidia runtime); NOT Docker Desktop
DC=(docker compose -f "$COMPOSE")

usage() {
  cat <<'HELP'
vllm-bench — on-demand vLLM GPU bench (B111). Run on rogueone.

  start    bring vLLM up on the native GPU engine (first run downloads the model ~5.5GB)
  stop     tear down + free VRAM (model stays cached in the hf-cache volume)
  status   container state + /v1/models
  logs     follow vLLM logs (Ctrl+C to detach)
  smoke    local completion sanity check (direct to :8001, not through Bifrost)

Notes: keep Ollama idle during a bench (shared 16GB). To swap the model, edit the compose --model/--gpu-memory-utilization.
HELP
}

case "${1:-}" in
  start)
    "${DC[@]}" up -d vllm
    echo "starting on the native GPU engine — watch with: $0 logs   (ready when: $0 status shows the model)"
    ;;
  stop)
    "${DC[@]}" down
    echo "stopped; VRAM freed (model cached for next start)."
    ;;
  status)
    "${DC[@]}" ps
    echo "--- /v1/models ---"
    curl -s http://localhost:8001/v1/models | { jq -r '.data[].id' 2>/dev/null || cat; } || echo "not serving yet (still loading, or run: $0 start)"
    ;;
  logs)
    "${DC[@]}" logs -f vllm
    ;;
  smoke)
    m="$(curl -s http://localhost:8001/v1/models | jq -r '.data[0].id' 2>/dev/null || true)"
    [ -z "${m:-}" ] && { echo "vLLM not serving — run: $0 start"; exit 1; }
    echo "model: $m"
    curl -s http://localhost:8001/v1/chat/completions -H 'Content-Type: application/json' -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"say hi in 3 words\"}],\"max_tokens\":16}" | { jq -r '.choices[0].message.content' 2>/dev/null || cat; }
    ;;
  *)
    usage
    [ -z "${1:-}" ] && exit 1 || exit 0
    ;;
esac
