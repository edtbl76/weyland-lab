#!/usr/bin/env bash
# seal_realm_gateway.sh — seal the two secrets for the Realm behind Bifrost's Agent Gateway (B249, 2026-11-19), from
# the gitignored scripts/.env, writing the COMPLETE SealedSecret files into the repo:
#   realm-gateway-token     REALM_GATEWAY_TOKEN — Bifrost sends it to the Realm on every call it forwards (runtime_auth
#                           `env.REALM_GATEWAY_TOKEN`); the Realm honours `allow_paid` only when it arrives.
#   weyland-operator-realm  REALM_GATEWAY_VK    — the operator's Bifrost virtual key `realm-operator`, from
#                           register_bifrost_realm_agent.py ensure-vk (appended to scripts/.env, never displayed).
#
# Fail closed: a missing or empty value stops the run naming it, and NOTHING is sealed. Values go to kubectl through
# stdin (never the command line, so never in the process list) and are never printed. Run on a box with kubectl +
# kubeseal + cluster access, like seal_bifrost_keys.sh. Runbook: docs/runbooks/realm-of-agents.md.
#
# Exit: 0 sealed · 1 a value missing · 2 could not run (no .env)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${REALM_ENV_FILE:-$HOME/IdeaProjects/weyland/scripts/.env}"
OUT_DIR="${SEAL_OUT_DIR:-$SCRIPT_DIR/../k8s/sealed-secrets/sealed}"
NS=weyland
CTRL_NS="${SEALED_SECRETS_CONTROLLER_NS:-kube-system}"
CTRL_NAME="${SEALED_SECRETS_CONTROLLER_NAME:-sealed-secrets-controller}"

[ -f "$ENV_FILE" ] || { echo "cannot read $ENV_FILE (the gitignored .env with the two values)" >&2; exit 2; }
set -a
# The gitignored .env, its path chosen at run time:
# shellcheck source=/dev/null
. "$ENV_FILE"
set +a

# secret name : key — both are checked before anything is sealed
PAIRS="realm-gateway-token:REALM_GATEWAY_TOKEN weyland-operator-realm:REALM_GATEWAY_VK"
missing=""
for pair in $PAIRS; do
  key="${pair#*:}"
  [ -n "${!key:-}" ] || missing="$missing $key"
done
if [ -n "$missing" ]; then
  echo "missing in $ENV_FILE:$missing — nothing sealed" >&2
  exit 1
fi

for pair in $PAIRS; do
  name="${pair%%:*}" key="${pair#*:}"
  out="$OUT_DIR/${NS}__${name}.yaml"
  printf '%s' "${!key}" \
    | kubectl create secret generic "$name" -n "$NS" --from-file="$key=/dev/stdin" --dry-run=client -o yaml \
    | kubeseal --controller-name "$CTRL_NAME" --controller-namespace "$CTRL_NS" --format yaml > "$out"
  echo "wrote sealed manifest: $out ($key)" >&2
done
echo "next: push the two files (Argo applies them); Bifrost, the Realm and the operator read them on their next start." >&2
