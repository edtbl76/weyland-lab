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
HUGGING_FACE_API_KEY OPENCODE_ZEN_API_KEY REPLICATE_API_KEY RUNWAY_API_KEY RUNWARE_API_KEY \
ELEVEN_LABS_API_KEY TOGETHER_API_KEY"

# PER-CONSUMER KEYS (2026-10-17, after the OpenCode exposure): Bifrost's own Anthropic and OpenAI keys live in .env as
# ANTHROPIC_BIFROST_KEY / OPENAI_BIFROST_KEY and are sealed under the names Bifrost already reads (ANTHROPIC_API_KEY /
# OPENAI_API_KEY), so bifrost.yaml and the env.VAR provider refs are unchanged. Both are REQUIRED — a missing one stops
# the run instead of sealing a secret without it (which would silently drop that provider). docs/runbooks/secrets-map.md.
declare -A SOURCE=( [ANTHROPIC_API_KEY]=ANTHROPIC_BIFROST_KEY [OPENAI_API_KEY]=OPENAI_BIFROST_KEY )
args=()
for var in $VARS; do
  src="${SOURCE[$var]:-$var}"
  val="${!src:-}"
  if [ -z "$val" ]; then
    if [ -n "${SOURCE[$var]:-}" ]; then echo "ERROR: $src missing in $ENV_FILE — Bifrost's own key is required" >&2; exit 1; fi
    echo "WARN: $var missing in .env — skipped" >&2; continue
  fi
  args+=( "--from-literal=$var=$val" )
done
[ ${#args[@]} -eq 0 ] && { echo "ERROR: no keys found in $ENV_FILE" >&2; exit 1; }

kubectl create secret generic "$NAME" -n "$NS" "${args[@]}" --dry-run=client -o yaml \
  | kubeseal --controller-name "$CTRL_NAME" --controller-namespace "$CTRL_NS" --format yaml \
  > "$OUT"

echo "wrote sealed manifest: $OUT  (${#args[@]} keys)" >&2
echo "next: apply it (push -> Argo, or kubectl apply -f), then the bifrost.yaml envFrom, then restart Bifrost." >&2
