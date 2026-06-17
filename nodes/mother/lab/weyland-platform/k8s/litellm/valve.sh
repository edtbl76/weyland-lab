#!/usr/bin/env bash
# LiteLLM valve: human-only cut-off for off-LAN hosted-model egress (Gemini/OpenRouter).
# Run on mother (has k3s/kubectl). The agent has no kubectl and /mcp-act does not expose it,
# so this control is outside the agent's reach by design.
#   ./valve.sh close   -> scale to 0 (drops in-flight; Claude turns fail closed)
#   ./valve.sh open    -> scale to 1
#   ./valve.sh status  -> replica state
set -euo pipefail
NS=weyland
DEP=litellm
case "${1:-status}" in
  close)  kubectl scale deploy/$DEP -n $NS --replicas=0; echo "CLOSED — Claude egress down" ;;
  open)   kubectl scale deploy/$DEP -n $NS --replicas=1; echo "OPEN — Claude egress up" ;;
  status) kubectl get deploy/$DEP -n $NS -o wide ;;
  *)      echo "usage: $0 {open|close|status}"; exit 1 ;;
esac
