#!/usr/bin/env bash
# B106 — PR-Agent (Qodo Merge OSS) review of a GitHub PR, routed through the lab's OWN LiteLLM/Bifrost gateway
# ($0 — your models, cost-tracked per-VK, no vendor egress). Runs on rogueone, which reaches BOTH the public
# GitHub repo AND the LAN gateway (:30400). A GitHub-cloud Action can't reach the LAN gateway — that's why this
# is a local CLI, not a workflow. Secrets come from the gitignored scripts/.env (NEVER committed).
#   usage: scripts/pr-agent-review.sh <github-pr-url> [review|describe|improve|ask]   (default: review)
#   env (scripts/.env):  LITELLM_API_KEY (required) · GITHUB_USER_TOKEN (required, repo-scoped PAT)
#   optional:      PR_AGENT_MODEL (default openai/wl-coding) · LITELLM_API_BASE (default http://192.168.1.243:30400)
#                  PR_AGENT_IMAGE (default qodoai/pr-agent:latest — verify the current tag at install)
set -euo pipefail
PR_URL="${1:?usage: pr-agent-review.sh <github-pr-url> [review|describe|improve|ask]}"
CMD="${2:-review}"
here="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$here/scripts/.env" ] && { set -a; . "$here/scripts/.env"; set +a; }
: "${LITELLM_API_KEY:?set LITELLM_API_KEY in scripts/.env}"
: "${GITHUB_USER_TOKEN:?set GITHUB_USER_TOKEN in scripts/.env (a repo-scoped GitHub PAT)}"
MODEL="${PR_AGENT_MODEL:-openai/wl-coding}"
API_BASE="${LITELLM_API_BASE:-http://192.168.1.243:30400}"
IMAGE="${PR_AGENT_IMAGE:-qodoai/pr-agent:latest}"
exec docker run --rm \
  -e CONFIG__MODEL="$MODEL" \
  -e OPENAI__KEY="$LITELLM_API_KEY" \
  -e OPENAI__API_BASE="$API_BASE" \
  -e GITHUB__USER_TOKEN="$GITHUB_USER_TOKEN" \
  -e GITHUB__DEPLOYMENT_TYPE=user \
  -v "$here/.pr_agent.toml:/app/pr_agent/settings/.pr_agent.toml:ro" \
  "$IMAGE" --pr_url "$PR_URL" "$CMD"
