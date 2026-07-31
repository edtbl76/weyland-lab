#!/usr/bin/env bash
set -euo pipefail
#
# sglang-bench — start/stop the on-demand SGLang GPU server (B111).
#
# SGLang's role in the lab = PREFIX CACHING (RadixAttention) for agent/RAG workloads (fat repeated system
# prompts / RAG context). Drives the committed compose, FORCING the native Docker engine (Desktop has no GPU).
# Run ON rogueone. Model = unsloth/Llama-3.2-1B-Instruct (ungated mirror; RadixAttention on by default).
# Run one GPU bench at a time — stop the vllm bench first if it's up (scripts/vllm-bench.sh stop).
#
# Docs: docs/runbooks/gpu-inference.md · docs/demos/gpu-inference.md
#
# Usage: scripts/sglang-bench.sh {start|stop|status|logs|smoke|prefix-bench}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GPU_DIR="$SCRIPT_DIR/../nodes/rogueone/services/gpu-inference"
COMPOSE="$GPU_DIR/docker-compose.yml"
export DOCKER_HOST="unix:///var/run/docker.sock"    # native engine (nvidia runtime); NOT Docker Desktop
DC=(docker compose -f "$COMPOSE")

usage() {
  cat <<'HELP'
sglang-bench — on-demand SGLang GPU server (B111). Run on rogueone.

  start         bring SGLang up on the native GPU engine (first run downloads the model)
  stop          tear down + free VRAM (model stays cached in the hf-cache volume)
  status        container state + /v1/models
  logs          follow SGLang logs (Ctrl+C to detach)
  smoke         local completion sanity check (direct to :8002, not through Bifrost)
  prefix-bench  RadixAttention prefix-cache bench — shared-prefix (cache hits) vs unique-prefix (misses), TTFT

Notes: SGLang = the lab's prefix-caching engine. Run one GPU bench at a time (stop vllm first). RadixAttention
is ON by default — no flag needed. Keep Ollama idle during a bench (shared 16GB).
HELP
}

case "${1:-}" in
  start)
    "${DC[@]}" up -d sglang
    echo "starting SGLang on the native GPU engine — watch: $0 logs   (ready when: $0 status shows the model)"
    ;;
  stop)
    "${DC[@]}" rm -sf sglang
    echo "SGLang stopped; VRAM freed (model cached for next start)."
    ;;
  status)
    "${DC[@]}" ps sglang
    echo "--- /v1/models ---"
    curl -s http://localhost:8002/v1/models | { jq -r '.data[].id' 2>/dev/null || cat; } || echo "not serving yet (still loading, or run: $0 start)"
    ;;
  logs)
    "${DC[@]}" logs -f sglang
    ;;
  smoke)
    m="$(curl -s http://localhost:8002/v1/models | jq -r '.data[0].id' 2>/dev/null || true)"
    [ -z "${m:-}" ] && { echo "SGLang not serving — run: $0 start"; exit 1; }
    echo "model: $m"
    curl -s http://localhost:8002/v1/chat/completions -H 'Content-Type: application/json' -d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"say hi in 3 words\"}],\"max_tokens\":16}" | { jq -r '.choices[0].message.content' 2>/dev/null || cat; }
    ;;
  prefix-bench)
    python3 "$GPU_DIR/prefix_cache_bench.py"
    ;;
  *)
    usage
    [ -z "${1:-}" ] && exit 1 || exit 0
    ;;
esac
