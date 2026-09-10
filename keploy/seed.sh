#!/usr/bin/env bash
# Traffic generator for the Keploy recording of the golden-python-fastapi service.
# This service is a stateless golden path (no CRUD / no downstream deps): it serves
# GET /health /ready /hello /metrics. So the seed just exercises each read endpoint a
# couple of times. Keploy captures the request/response pairs as the test corpus.
#
# Used during `keploy record`; after recording, this file is committed inside the
# recorded test-set's folder (keploy/test-set-N/seed.sh).
set -uo pipefail
# Same-port 8091 (app moved off 8080 because Ray owns 8080 on rogueone; recorded port must equal the
# app's real port, so no host≠container remap).
BASE="${BASE:-http://localhost:8091}"

# wait for the app (Keploy launches it) to answer
for i in $(seq 1 30); do
  curl -sf "$BASE/health" >/dev/null 2>&1 && break
  sleep 1
done

# NB: /metrics is deliberately NOT recorded — its Prometheus body changes every scrape
# (counters, memory, gc), so it's a poor deterministic regression target. The stable
# contract endpoints (/health /ready /hello) are what we assert.
for _ in 1 2; do
  curl -s "$BASE/health" >/dev/null
  curl -s "$BASE/ready"  >/dev/null
  curl -s "$BASE/hello"  >/dev/null
done
echo "seed: drove /health /ready /hello ×2"
