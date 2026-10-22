#!/usr/bin/env bash
# test-proxy.sh (B211, 2026-10-22) — prove the rogueone Ollama front door against a REAL Ollama before it is deployed.
#
# Runs ollama/ollama (the version rogueone runs) bound to 127.0.0.1 inside its own container, and the repo's nginx.conf
# in that container's network namespace, exactly as on rogueone (Ollama on loopback, the proxy in front). A client in
# another container is a "remote" caller, the role every cluster pod plays (their traffic reaches rogueone from mother).
# The test swaps only the three site files: it listens on 0.0.0.0:8080, treats 127.0.0.1 as the only local source,
# and uses a throwaway token. The real token never enters this script.
#
#   usage: nodes/rogueone/ollama-proxy/test-proxy.sh        (needs docker; pulls ollama, nginx and curl images once)
# EXIT: 0 every case passed · 1 a case failed, named · 2 could not run (no docker, a container that never came up).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OLLAMA_IMAGE="${OLLAMA_IMAGE:-ollama/ollama:0.31.2}"
NGINX_IMAGE="$(sed -n 's/^Environment=NGINX_IMAGE=//p' "$HERE/../systemd/ollama-proxy.service")"
CURL_IMAGE="${CURL_IMAGE:-curlimages/curl:8.11.1}"
ID="ollama-proxy-test-$$"
T="$(mktemp -d)"

command -v docker >/dev/null 2>&1 || { echo "CANNOT RUN: docker not found" >&2; exit 2; }
[ -n "$NGINX_IMAGE" ] || { echo "CANNOT RUN: no NGINX_IMAGE= line in ollama-proxy.service" >&2; exit 2; }

# shellcheck disable=SC2329  # invoked by the EXIT trap
cleanup() { docker rm -f "$ID-ollama" "$ID-proxy" >/dev/null 2>&1 || true; docker network rm "$ID" >/dev/null 2>&1 || true; rm -rf "$T"; }
trap cleanup EXIT

mkdir -p "$T/site"
cp "$HERE/upstream.conf" "$T/site/upstream.conf"
printf 'listen 0.0.0.0:8080;\n' > "$T/site/listen.conf"
printf '127.0.0.1 1;\n' > "$T/site/local-sources.conf"
printf '"Bearer test-token" 1;\n' > "$T/token.map"

docker network create "$ID" >/dev/null
docker run -d --name "$ID-ollama" --network "$ID" -e OLLAMA_HOST=127.0.0.1:11434 "$OLLAMA_IMAGE" >/dev/null
docker run -d --name "$ID-proxy" --network "container:$ID-ollama" \
  -v "$HERE/nginx.conf:/etc/nginx/nginx.conf:ro" -v "$T/site:/etc/ollama-proxy:ro" \
  -v "$T/token.map:/run/secrets/ollama-proxy-token.map:ro" "$NGINX_IMAGE" >/dev/null

ip="$(docker inspect -f "{{(index .NetworkSettings.Networks \"$ID\").IPAddress}}" "$ID-ollama")"
remote() { docker run --rm --network "$ID" "$CURL_IMAGE" -s -o /dev/null -w '%{http_code}' --max-time 20 "$@"; }
# A local caller: a curl container sharing the Ollama container's namespace, so its source is 127.0.0.1.
local_() { docker run --rm --network "container:$ID-ollama" "$CURL_IMAGE" -s -o /dev/null -w '%{http_code}' --max-time 20 "$@"; }

up=0
for _ in $(seq 1 30); do
  [ "$(local_ http://127.0.0.1:8080/api/version 2>/dev/null)" = "200" ] && { up=1; break; }
  sleep 1
done
[ "$up" = 1 ] || { echo "CANNOT RUN: Ollama behind the proxy never answered /api/version" >&2; docker logs "$ID-proxy" 2>&1 | tail -5 >&2; exit 2; }

fail=0
check() {  # check <name> <expected code> <actual code>
  if [ "$3" = "$2" ]; then echo "ok   $1 ($3)"; else echo "FAIL $1: expected $2, got $3"; fail=1; fi
}
check "remote, no token → refused"                401 "$(remote "http://$ip:8080/api/version")"
check "remote, wrong token → refused"             401 "$(remote -H 'Authorization: Bearer nope' "http://$ip:8080/api/version")"
check "remote, token → served"                    200 "$(remote -H 'Authorization: Bearer test-token' "http://$ip:8080/api/version")"
check "remote, token, OpenAI /v1/models → served" 200 "$(remote -H 'Authorization: Bearer test-token' "http://$ip:8080/v1/models")"
check "remote, token, /api/pull → forbidden"      403 "$(remote -H 'Authorization: Bearer test-token' -X POST -d '{"model":"x"}' "http://$ip:8080/api/pull")"
check "remote, token, /api/delete → forbidden"    403 "$(remote -H 'Authorization: Bearer test-token' -X DELETE -d '{"model":"x"}' "http://$ip:8080/api/delete")"
check "remote, no token, /api/pull → forbidden"   403 "$(remote -X POST -d '{"model":"x"}' "http://$ip:8080/api/pull")"
check "local, no token → served"                  200 "$(local_ http://127.0.0.1:8080/api/version)"
# Ollama's own answer (404 model not found) proves a local management call reaches it rather than the proxy's 403.
check "local, /api/delete → reaches Ollama"       404 "$(local_ -X DELETE -d '{"model":"no-such-model"}' http://127.0.0.1:8080/api/delete)"

[ "$fail" = 0 ] && echo "OK — the proxy admits only the token from a remote source and never forwards model management."
exit "$fail"
