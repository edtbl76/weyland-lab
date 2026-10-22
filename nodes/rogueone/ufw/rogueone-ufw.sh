#!/usr/bin/env bash
# rogueone-ufw.sh (B211, 2026-10-22) — the firewall rules for rogueone's LAN-reachable service ports, in git.
#
# WHY: the rules lived only in two runbooks and in rogueone's ufw, which only root can read, so nothing could notice a
# rule going missing. These ports matter: Basic Memory (:8765) has no auth, and Ollama's front door (:11434) is the one
# path the cluster has to the GPU. ufw is first-match, so each port is its ALLOWs first, then a DENY for everyone else.
#   :11434  Ollama's front door (ollama-proxy.service): mother (every pod arrives SNATed to it) + docker0 (OpenHands).
#           The proxy also asks mother's callers for the bearer token; ufw keeps the rest of the LAN off it entirely.
#   :8765   Basic Memory (B182): mother only (Bifrost).
#
#   sudo nodes/rogueone/ufw/rogueone-ufw.sh --apply    idempotent (ufw skips a rule it already has)
#   sudo nodes/rogueone/ufw/rogueone-ufw.sh --check    exit 0 in place · 1 drift, named · 2 cannot check
# SEAMS: UFW_STATUS_FILE (read this instead of `ufw status numbered`), UFW_DRY_RUN=1 (print the --apply commands).
# Tests: scripts/tests/rogueone-ufw.bats. Runbook: docs/runbooks/model-serving-ollama.md § Front door.
set -euo pipefail

# port|source — the ALLOWs, in order. Each port listed here also gets a DENY after its ALLOWs.
ALLOWS=(
  "11434|192.168.1.243"
  "11434|172.17.0.0/16"
  "8765|192.168.1.243"
)
PORTS=(11434 8765)

usage() { echo "usage: $0 --apply | --check" >&2; exit 2; }
[ $# -eq 1 ] || usage

apply() {
  local run=(ufw)
  [ "${UFW_DRY_RUN:-0}" = 1 ] && run=(echo ufw)
  local a
  for a in "${ALLOWS[@]}"; do
    "${run[@]}" allow from "${a#*|}" to any port "${a%%|*}" proto tcp
  done
  local p
  for p in "${PORTS[@]}"; do
    "${run[@]}" deny "$p/tcp"
  done
}

check() {
  local status
  if [ -n "${UFW_STATUS_FILE:-}" ]; then
    status="$(cat "$UFW_STATUS_FILE")"
  else
    status="$(ufw status numbered)" || { echo "CANNOT CHECK: \`ufw status numbered\` failed (run with sudo)"; exit 2; }
  fi
  grep -q '^Status: active' <<<"$status" || { echo "CANNOT CHECK: ufw is not active"; exit 2; }

  # "[ 3] 11434/tcp   ALLOW IN   192.168.1.243" -> "3 11434/tcp ALLOW 192.168.1.243" (IPv4 rules only)
  local rules
  rules="$(awk '/^\[ *[0-9]+\]/ && !/\(v6\)/ {
      n=$0; sub(/^\[ */, "", n); sub(/\].*/, "", n)
      line=$0; sub(/^\[ *[0-9]+\] */, "", line); split(line, f, /  +/)
      act=f[2]; sub(/ IN$/, "", act)
      print n, f[1], act, f[3]
    }' <<<"$status")"
  [ -n "$rules" ] || { echo "CANNOT CHECK: no numbered rule parsed from ufw's output"; exit 2; }

  local drift=0 a port src allow_n deny_n
  for a in "${ALLOWS[@]}"; do
    port="${a%%|*}"; src="${a#*|}"
    allow_n="$(awk -v t="$port/tcp" -v s="$src" '$2==t && $3=="ALLOW" && $4==s {print $1; exit}' <<<"$rules")"
    deny_n="$(awk -v t="$port/tcp" '$2==t && $3=="DENY" && $4=="Anywhere" {print $1; exit}' <<<"$rules")"
    if [ -z "$allow_n" ]; then
      echo "MISSING: allow $port/tcp from $src"; drift=1
    elif [ -n "$deny_n" ] && [ "$deny_n" -lt "$allow_n" ]; then
      echo "ORDER: $port/tcp deny (rule $deny_n) is above allow from $src (rule $allow_n) — the allow never fires"
      drift=1
    fi
  done
  local p
  for p in "${PORTS[@]}"; do
    awk -v t="$p/tcp" '$2==t && $3=="DENY" && $4=="Anywhere" {f=1} END {exit !f}' <<<"$rules" \
      || { echo "MISSING: deny $p/tcp (the port is open to the whole LAN)"; drift=1; }
  done
  [ "$drift" = 0 ] || exit 1
  echo "OK — ${#PORTS[@]} port(s), ${#ALLOWS[@]} allow rule(s) and their denies in place, in order."
}

case "$1" in
  --apply) apply ;;
  --check) check ;;
  *) usage ;;
esac
