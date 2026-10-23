#!/usr/bin/env bash
# trino-credentials.sh (B233, 2026-10-23) — the credentials behind Trino's password front door.
#
# WHY: Trino 468 had no authenticator, so every caller self-asserted X-Trino-User and Ranger's per-user policies could
# be bypassed by claiming a privileged name. Each caller now has its own identity and password. The passwords live in
# scripts/.env (never typed, never printed); Trino gets their bcrypt hashes (password.db) plus a TLS cert from the lab's
# mkcert CA, because Trino accepts a password only over HTTPS.
#
#   scripts/trino-credentials.sh generate [--rotate <identity>]   fill missing TRINO_PW_* + TRINO_SHARED_SECRET in .env
#   scripts/trino-credentials.sh build <dir>                       password.db + tls.pem into <dir> (made 0700)
#   scripts/trino-credentials.sh apply <dir>                       create the Secrets (kubectl), check stored lengths
#   scripts/trino-credentials.sh seal                              SealedSecrets into k8s/sealed-secrets/sealed/
#
# Values reach kubectl as files in a private temp dir, never as command-line literals (ps would show them).
# SEAMS: ENV_FILE, HTPASSWD (a command taking `-niBC 10 <user>`, password on stdin), MKCERT, KUBECTL, KUBESEAL,
# SEALED_DIR. Tests: scripts/tests/trino-credentials.bats. Runbook: docs/runbooks/trino.md § Authentication.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/scripts/.env}"
MKCERT="${MKCERT:-mkcert}"
KUBECTL="${KUBECTL:-kubectl}"
KUBESEAL="${KUBESEAL:-kubeseal}"
SEALED_DIR="${SEALED_DIR:-$ROOT/nodes/mother/lab/weyland-platform/k8s/sealed-secrets/sealed}"
# httpd's htpasswd, pinned by digest (observed 2026-10-23: `-niBC 10 u` prints `u:$2y$10$…` and a blank line).
HTPASSWD_IMAGE="httpd:2.4-alpine@sha256:759a1d9178d351185978e41be37a3e91675a4ddc0653aa5df493cfd4c67e24ec"

# identity|secret — the namespace/name of the caller's Secret (keys username + password), or - when the credential
# is entered in an app's own UI (Lightdash, Superset), an IDE (IntelliJ) or Ranger's service config.
IDENTITIES=(
  "dbt|weyland/trino-dbt"                                # Dagster user-code (dbt, marts, Feast, GE, Soda) + dbt-docs
  "cube|data-mesh/trino-cube"
  "datahub|data-mesh/trino-datahub"                      # DataHub managed ingestion (runs in datahub-actions)
  "datahub-coverage|weyland/trino-datahub-coverage"     # the CronJob runs in weyland (manifest under k8s/monitoring/)
  "mcp|weyland/trino-mcp"
  "prometheus|data-mesh/trino-metrics-auth"              # the ServiceMonitor's basicAuth
  "notebook|jupyterhub/trino-notebook"
  "analyst|jupyterhub/trino-analyst"                     # Ranger's masked demo identity (notebook 72)
  "perf|data-mesh/trino-perf"                            # the on-demand k6 baseline Job (scripts/perf/trino-baseline.sh)
  "lightdash|-"
  "superset|-"
  "emangini|-"                                           # IntelliJ (Database tool) on rogueone
  "ranger|-"                                             # Ranger Admin's resource lookup (ranger_setup.py)
)
TRINO_SECRET="data-mesh/trino-auth"
# Every name a client reaches Trino by: the Service's DNS forms, and mother's IP for the trino-lan NodePort.
CERT_NAMES=(trino.data-mesh.svc.cluster.local trino.data-mesh.svc trino.data-mesh trino 192.168.1.243)

usage() { echo "usage: $0 generate [--rotate <identity>] | build <dir> | apply <dir> | seal" >&2; exit 2; }

env_key() { local id="${1^^}"; echo "TRINO_PW_${id//-/_}"; }
rand_hex() { od -An -tx1 -N"$1" /dev/urandom | tr -d ' \n'; }
env_value() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -1; }
known() { local e; for e in "${IDENTITIES[@]}"; do [ "${e%%|*}" = "$1" ] && return 0; done; return 1; }

htpw() {  # <user>, password on stdin -> "user:$2y$10$…"
  if [ -n "${HTPASSWD:-}" ]; then "$HTPASSWD" -niBC 10 "$1"
  else docker run --rm -i "$HTPASSWD_IMAGE" htpasswd -niBC 10 "$1"; fi
}

generate() {
  local rotate=""
  if [ $# -gt 0 ]; then
    [ "$1" = --rotate ] && [ $# -eq 2 ] || usage
    known "$2" || { echo "unknown identity: $2" >&2; exit 1; }
    rotate="$(env_key "$2")"
  fi
  touch "$ENV_FILE"
  if [ -n "$rotate" ]; then
    sed -i "/^$rotate=/d" "$ENV_FILE"
  fi
  local added=0 e k
  for e in "${IDENTITIES[@]}"; do
    k="$(env_key "${e%%|*}")"
    grep -q "^$k=." "$ENV_FILE" && continue
    printf '%s=%s\n' "$k" "$(rand_hex 24)" >> "$ENV_FILE"; added=$((added + 1))
  done
  if ! grep -q '^TRINO_SHARED_SECRET=.' "$ENV_FILE"; then
    printf 'TRINO_SHARED_SECRET=%s\n' "$(rand_hex 32)" >> "$ENV_FILE"; added=$((added + 1))
  fi
  echo "generate: added $added, kept $(( ${#IDENTITIES[@]} + 1 - added )) (values are in $ENV_FILE, not printed)"
}

require_all() {
  local e k
  for e in "${IDENTITIES[@]}"; do
    k="$(env_key "${e%%|*}")"
    [ -n "$(env_value "$k")" ] || { echo "$k is not set in $ENV_FILE (run: $0 generate)" >&2; exit 1; }
  done
  [ -n "$(env_value TRINO_SHARED_SECRET)" ] || { echo "TRINO_SHARED_SECRET is not set in $ENV_FILE" >&2; exit 1; }
}

build() {
  [ $# -eq 1 ] || usage
  local out="$1"
  require_all
  mkdir -p "$out"; chmod 700 "$out"
  local db="$out/password.db" e id
  : > "$db.tmp"
  for e in "${IDENTITIES[@]}"; do
    id="${e%%|*}"
    printf '%s' "$(env_value "$(env_key "$id")")" | htpw "$id" | grep -v '^$' >> "$db.tmp"
  done
  [ "$(grep -c '^[^:]*:\$2y\$' "$db.tmp")" -eq "${#IDENTITIES[@]}" ] || { rm -f "$db.tmp"; echo "build: bcrypt output incomplete" >&2; exit 1; }
  mv "$db.tmp" "$db"
  local log
  log="$("$MKCERT" -cert-file "$out/tls.crt" -key-file "$out/tls.key" "${CERT_NAMES[@]}" 2>&1)" \
    || { echo "$log" >&2; echo "build: mkcert failed" >&2; exit 1; }
  cat "$out/tls.key" "$out/tls.crt" > "$out/tls.pem"
  rm -f "$out/tls.key" "$out/tls.crt"
  echo "build: $db (${#IDENTITIES[@]} identities) + $out/tls.pem (${CERT_NAMES[*]})"
}

create() {  # <ns/name> <--from-file args...>
  local ref="$1"; shift
  "$KUBECTL" -n "${ref%%/*}" create secret generic "${ref#*/}" "$@" --dry-run=client -o yaml | "$KUBECTL" apply -f - >/dev/null
}

stored_len_ok() {  # <ns/name> <key> <plain length>
  local want=$(( ($3 + 2) / 3 * 4 )) got
  got="$("$KUBECTL" -n "${1%%/*}" get secret "${1#*/}" -o jsonpath="{.data.$2}" | wc -c)"
  [ "$got" -eq "$want" ] || { echo "$1/$2: stored value has the wrong length ($got, want $want)" >&2; return 1; }
}

apply() {
  [ $# -eq 1 ] || usage
  local out="$1"
  require_all
  [ -s "$out/password.db" ] && [ -s "$out/tls.pem" ] || { echo "apply: run build $out first" >&2; exit 1; }
  tmp="$(mktemp -d)"; chmod 700 "$tmp"   # global: the EXIT trap runs after this function's locals are gone
  trap 'rm -rf "$tmp"' EXIT
  printf '%s' "$(env_value TRINO_SHARED_SECRET)" > "$tmp/shared"
  create "$TRINO_SECRET" --from-file=password.db="$out/password.db" --from-file=tls.pem="$out/tls.pem" \
    --from-file=TRINO_SHARED_SECRET="$tmp/shared"
  stored_len_ok "$TRINO_SECRET" TRINO_SHARED_SECRET 64
  local e id ref n=1
  for e in "${IDENTITIES[@]}"; do
    id="${e%%|*}"; ref="${e#*|}"
    [ "$ref" = - ] && continue
    printf '%s' "$id" > "$tmp/username"
    printf '%s' "$(env_value "$(env_key "$id")")" > "$tmp/password"
    create "$ref" --from-file=username="$tmp/username" --from-file=password="$tmp/password"
    stored_len_ok "$ref" password 48
    n=$((n + 1))
  done
  echo "apply: $n secrets created, stored lengths checked"
}

seal() {
  [ $# -eq 0 ] || usage
  local refs=("$TRINO_SECRET") e ref
  for e in "${IDENTITIES[@]}"; do ref="${e#*|}"; [ "$ref" = - ] || refs+=("$ref"); done
  for ref in "${refs[@]}"; do
    "$KUBECTL" -n "${ref%%/*}" annotate secret "${ref#*/}" sealedsecrets.bitnami.com/managed=true --overwrite >/dev/null
    "$KUBECTL" -n "${ref%%/*}" get secret "${ref#*/}" -o yaml | "$KUBESEAL" --format yaml > "$SEALED_DIR/${ref%%/*}__${ref#*/}.yaml"
  done
  echo "seal: ${#refs[@]} SealedSecrets in $SEALED_DIR"
}

[ $# -ge 1 ] || usage
cmd="$1"; shift
case "$cmd" in
  generate) generate "$@" ;;
  build) build "$@" ;;
  apply) apply "$@" ;;
  seal) seal "$@" ;;
  *) usage ;;
esac
