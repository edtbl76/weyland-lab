#!/usr/bin/env bash
set -euo pipefail
#
# seal_bifrost_keys.sh — seal the Bifrost provider API keys from scripts/.env into a SealedSecret's encryptedData
# (weyland/bifrost-provider-keys), for B111 key-sealing. Run on a box with kubeseal + cluster access.
#
# Key VALUES come from .env and are NEVER printed — only the kubeseal-encrypted blobs are emitted. Paste the output
# into k8s/sealed-secrets/sealed/weyland__bifrost-provider-keys.yaml under `spec.encryptedData:`.
#
# The Secret data keys = the env var names, so `envFrom` on the Bifrost pod exposes them as env for `env.VAR` refs.
# Self-hosted providers (ollama/vllm/sgl) use dummy keys → intentionally NOT sealed.
#
# NOTE: the .env lives at REPO-ROOT scripts/.env, not here — adjust the source path if you moved it.

ENV_FILE="${BIFROST_ENV_FILE:-$HOME/IdeaProjects/weyland/scripts/.env}"
NS=weyland
NAME=bifrost-provider-keys

set -a; . "$ENV_FILE"; set +a

VARS="ANTHROPIC_API_KEY OPENAI_API_KEY GEMINI_API_KEY COHERE_API_KEY MISTRAL_API_KEY DEEPSEEK_API_KEY \
OPENROUTER_API_KEY PERPLEXITY_API_KEY FIREWORKS_API_KEY XAI_API_KEY CEREBRAS_API_KEY GROQ_API_KEY \
HUGGING_FACE_API_KEY OPENCODE_ZEN_API_KEY PARASAIL_API_KEY REPLICATE_API_KEY RUNWAY_API_KEY RUNWARE_API_KEY \
WAFER_API_KEY ELEVEN_LABS_API_KEY TOGETHER_API_KEY"

echo "  encryptedData:"
for var in $VARS; do
  val="${!var:-}"
  if [ -z "$val" ]; then
    echo "    # $var: (MISSING in .env — skipped)" >&2
    continue
  fi
  enc="$(printf '%s' "$val" | kubeseal --raw --namespace "$NS" --name "$NAME" --scope strict)"
  echo "    $var: $enc"
done
echo "# ^ paste the block above into k8s/sealed-secrets/sealed/weyland__bifrost-provider-keys.yaml" >&2
