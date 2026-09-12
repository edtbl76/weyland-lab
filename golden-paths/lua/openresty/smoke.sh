#!/bin/sh
# Ephemeral smoke (Lua/OpenResty) — start the built OpenResty server, poll /ready, assert /hello's known
# payload, exit. Run as the Job's container command (via .smoke), so it self-tests the real image and exits.
set -u
openresty -p /app -c /app/nginx.conf -g 'daemon off;' &
pid=$!
for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:8080/ready >/dev/null 2>&1 && break
  kill -0 "$pid" 2>/dev/null || { echo "SMOKE FAIL: server exited" >&2; exit 1; }
  sleep 0.5
done
if curl -sf http://127.0.0.1:8080/hello 2>/dev/null | grep -q 'hello, weyland'; then
  echo "SMOKE OK: image serves"; kill "$pid" 2>/dev/null; exit 0
fi
echo "SMOKE FAIL: /hello did not return the known payload" >&2; kill "$pid" 2>/dev/null; exit 1
