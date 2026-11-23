#!/usr/bin/env bash
# keycloak-tofu.sh — reconcile the `weyland` realm and its clients from code (tofu/keycloak/), with every credential
# loaded into the environment and none printed (B256, 2026-11-23; replaces exporting three variables by hand).
#   MinIO (state backend): AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from the gitignored scripts/.env
#   Keycloak admin:        the bootstrap admin password, read from the keycloak-secret Secret straight into the env
#   operator_password:     only Keycloak's initial_password when the realm user is FIRST created (inert since), so the
#                          same value is passed rather than asking anyone to type a password
# Runbook: docs/runbooks/keycloak.md § Realm and clients as code.
#
#   usage: keycloak-tofu.sh plan|apply
#   EXIT: tofu's own exit code · 2 usage or a missing credential (named; nothing ran)
set -euo pipefail
mode="${1:-}"
case "$mode" in plan|apply) ;; *) echo "usage: keycloak-tofu.sh plan|apply" >&2; exit 2 ;; esac

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${KEYCLOAK_TOFU_ENV:-$REPO/scripts/.env}"   # test seam
# shellcheck source=/dev/null  # a gitignored env file (or the test seam)
[ -f "$ENV_FILE" ] && { set -a; . "$ENV_FILE"; set +a; }
[ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_SECRET_ACCESS_KEY:-}" ] || {
  echo "keycloak-tofu: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY missing from scripts/.env (the MinIO state backend)" >&2; exit 2; }

TF_VAR_kc_admin_password="$(kubectl -n weyland get secret keycloak-secret -o jsonpath='{.data.KC_BOOTSTRAP_ADMIN_PASSWORD}' | base64 -d)"
[ -n "$TF_VAR_kc_admin_password" ] || { echo "keycloak-tofu: could not read the Keycloak admin password from keycloak-secret" >&2; exit 2; }
export TF_VAR_kc_admin_password TF_VAR_operator_password="$TF_VAR_kc_admin_password"

exec tofu -chdir="$REPO/nodes/mother/lab/weyland-platform/tofu/keycloak" "$mode"
