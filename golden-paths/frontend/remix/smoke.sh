#!/bin/sh
# Ephemeral smoke (Frontend/Remix) — start remix-serve, poll /ready, assert /hello's payload and the
# SSR-rendered demo route both carry the greeting, exit.
set -u
PORT=8080 ./node_modules/.bin/remix-serve ./build/server/index.js &
pid=$!
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:8080/ready >/dev/null 2>&1 && break
  kill -0 "$pid" 2>/dev/null || { echo "SMOKE FAIL: server exited" >&2; exit 1; }
  sleep 0.5
done
if curl -sf http://127.0.0.1:8080/hello 2>/dev/null | grep -q 'hello, weyland' \
   && curl -sf http://127.0.0.1:8080/ 2>/dev/null | grep -q 'hello, weyland'; then
  echo "SMOKE OK: image serves + SSR-renders"; kill "$pid" 2>/dev/null; exit 0
fi
echo "SMOKE FAIL: /hello or the demo route did not carry the greeting" >&2; kill "$pid" 2>/dev/null; exit 1
