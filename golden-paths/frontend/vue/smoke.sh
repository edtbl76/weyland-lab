#!/bin/sh
# Ephemeral smoke (Frontend/Vue) — start the static server, poll /ready, assert /hello + the served
# bundle both carry the known payload, exit.
set -u
node server.mjs &
pid=$!
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:8080/ready >/dev/null 2>&1 && break
  kill -0 "$pid" 2>/dev/null || { echo "SMOKE FAIL: server exited" >&2; exit 1; }
  sleep 0.5
done
if curl -sf http://127.0.0.1:8080/hello 2>/dev/null | grep -q 'hello, weyland' \
   && curl -sf http://127.0.0.1:8080/ 2>/dev/null | grep -q 'golden-frontend-vue'; then
  echo "SMOKE OK: image serves + renders"; kill "$pid" 2>/dev/null; exit 0
fi
echo "SMOKE FAIL: /hello or the demo route did not carry the known payload" >&2; kill "$pid" 2>/dev/null; exit 1
