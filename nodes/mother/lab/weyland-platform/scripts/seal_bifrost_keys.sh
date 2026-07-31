#!/usr/bin/env bash
set -euo pipefail
#
# seal_bifrost_keys.sh — seal the Bifrost provider API keys from scripts/.env into the SealedSecret manifest,
# writing the COMPLETE file directly (no manual paste). B111 key-sealing.
#
# It builds a Secret from .env in memory (--dry-run, never applied) and pipes it through kubeseal, which emits the
# full SealedSecret (encryptedData + template) to k8s/sealed-secrets/sealed/weyland__bifrost-provider-keys.yaml.
# Key VALUES never touch disk in plaintext and are never printed. Run on a box with kubectl + kubeseal + cluster access.
#
# The Secret's data keys = the env var names, so `envFrom` on the Bifrost pod exposes them for `env.VAR` refs.
# Self-hosted providers (ollama/vllm/sgl) use dummy keys → intentionally NOT sealed.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BIFROST_ENV_FILE:-$HOME/IdeaProjects/weyland/scripts/.env}"
OUT="$SCRIPT_DIR/../k8s/sealed-secrets/sealed/weyland__bifrost-provider-keys.yaml"
NS=weyland
NAME=bifrost-provider-keys
CTRL_NS="${SEALED_SECRETS_CONTROLLER_NS:-kube-system}"
CTRL_NAME="${SEALED_SECRETS_CONTROLLER_NAME:-sealed-secrets-controller}"

set -a; . "$ENV_FILE"; set +a

VARS="ANTHROPIC_API_KEY OPENAI_API_KEY GEMINI_API_KEY COHERE_API_KEY MISTRAL_API_KEY DEEPSEEK_API_KEY \
OPENROUTER_API_KEY PERPLEXITY_API_KEY FIREWORKS_API_KEY XAI_API_KEY CEREBRAS_API_KEY GROQ_API_KEY \
HUGGING_FACE_API_KEY OPENCODE_ZEN_API_KEY PARASAIL_API_KEY REPLICATE_API_KEY RUNWAY_API_KEY RUNWARE_API_KEY \
WAFER_API_KEY ELEVEN_LABS_API_KEY TOGETHER_API_KEY"

args=()
for var in $VARS; do
  val="${!var:-}"
  if [ -z "$val" ]; then echo "WARN: $var missing in .env — skipped" >&2; continue; fi
  args+=( "--from-literal=$var=$val" )
done
[ ${#args[@]} -eq 0 ] && { echo "ERROR: no keys found in $ENV_FILE" >&2; exit 1; }

kubectl create secret generic "$NAME" -n "$NS" "${args[@]}" --dry-run=client -o yaml \
  | kubeseal --controller-name "$CTRL_NAME" --controller-namespace "$CTRL_NS" --format yaml \
  > "$OUT"

echo "wrote sealed manifest: $OUT  (${#args[@]} keys)" >&2
echo "next: apply it (push -> Argo, or kubectl apply -f), then the bifrost.yaml envFrom, then restart Bifrost." >&2
