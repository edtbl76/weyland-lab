#!/usr/bin/env bats
# The rogueone Ollama front door (B211, 2026-10-22): nodes/rogueone/ollama-proxy/ + systemd/ollama-proxy.service.
# Behaviour is proven against a REAL Ollama by nodes/rogueone/ollama-proxy/test-proxy.sh (needs Docker, which this lane
# does not have). These pin the invariants a careless edit would break silently: the proxy must never claim 0.0.0.0
# (Ollama's own loopback port), mother must never count as a local source (every pod arrives from it), remote model
# management stays refused, the token is never forwarded, Ollama stays on loopback, and the token never sits in git.

setup() {
  D="$BATS_TEST_DIRNAME/../../nodes/rogueone/ollama-proxy"
  U="$BATS_TEST_DIRNAME/../../nodes/rogueone/systemd"
}

@test "the proxy listens only on rogueone's LAN and docker0 addresses, never 0.0.0.0" {
  run grep -E '^\s*listen' "$D/listen.conf"
  [ "$status" -eq 0 ]
  [ "$(echo "$output" | wc -l)" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"192.168.1.230:11434"* && "$output" == *"172.17.0.1:11434"* ]] || { echo "$output"; return 1; }
  if grep -Eq '^\s*listen\s+(0\.0\.0\.0|\[::\]|11434)' "$D/listen.conf"; then return 1; fi
}

@test "mother is not a local source (every pod's traffic arrives from it)" {
  if grep -Eq '^\s*192\.168\.1\.243|^\s*192\.168\.1\.0/24|^\s*0\.0\.0\.0/0' "$D/local-sources.conf"; then return 1; fi
  grep -Eq '^\s*127\.0\.0\.1\s+1;' "$D/local-sources.conf"
}

@test "remote model management is refused before the token is considered" {
  grep -Eq 'api/\(pull\|push\|create\|copy\|delete\|blobs\)' "$D/nginx.conf"
  grep -Eq '"01" 1;' "$D/nginx.conf"
  # the 403 check comes before the 401 check inside the location
  [ "$(grep -n 'refuse_management) { return 403' "$D/nginx.conf" | cut -d: -f1)" -lt "$(grep -n 'admitted = 0) { return 401' "$D/nginx.conf" | cut -d: -f1)" ]
}

@test "admission defaults to refused and the token is never forwarded to Ollama" {
  # shellcheck disable=SC2016  # a literal nginx variable name, not a shell expansion
  run sed -n '/map "\$local_source\$token_ok" \$admitted/,/}/p' "$D/nginx.conf"
  [[ "$output" == *"default 0;"* ]] || { echo "$output"; return 1; }
  [[ "$output" != *'"00" 1'* ]] || { echo "$output"; return 1; }
  grep -Fq 'proxy_set_header Authorization "";' "$D/nginx.conf"
}

@test "the upstream is Ollama on loopback, and Ollama itself binds loopback" {
  grep -Eq 'server 127\.0\.0\.1:11434;' "$D/upstream.conf"
  run grep -E '^Environment="OLLAMA_HOST=' "$U/ollama-host.conf"
  [[ "$output" == *'OLLAMA_HOST=127.0.0.1:11434"'* ]] || { echo "$output"; return 1; }
}

@test "the token map is mounted from outside git, read-only, and no token file is committed" {
  grep -Fq -- '-v /etc/ollama-proxy-secret/token.map:/run/secrets/ollama-proxy-token.map:ro' "$U/ollama-proxy.service"
  [ ! -e "$D/token.map" ]
  if grep -rEq '"Bearer [^"]+" 1;' "$D"/*.conf; then return 1; fi
}

@test "the proxy image is pinned by digest" {
  grep -Eq '^Environment=NGINX_IMAGE=nginx@sha256:[0-9a-f]{64}$' "$U/ollama-proxy.service"
}
