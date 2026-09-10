# Runbook — API client (Bruno) + API-regression capture (Keploy) (B104)

Two paired, $0/OSS, Git-native API tools. **Bruno** is the hand-authored, assertion-driven client
(collections as committed `.bru` files). **Keploy** records real inbound traffic via eBPF and generates
committed regression test-sets + dependency mocks that `keploy test` replays and diffs. Both complement
the machine-readable API-lifecycle catalog (`apis.yaml`, B155) and the API contract-lock (B152) — those
govern; these exercise.

## Bruno — run the collection (free, no privileges)

Collection: `bruno/weyland/` (see its README for layout + how to add requests).

```
cd bruno/weyland
npx --yes @usebruno/cli run tool-server gateway --env lan     # keyless smoke, all green (5 req / 10 assert)
npx --yes @usebruno/cli run authenticated --env lan --env-var gw_key=$LITELLM_MASTER_KEY
```

The keyless run asserts health/ready/metrics on the tool-server (`:30080`) and LiteLLM gateway
(`:30400`) — the same request-serving plane the perf baseline measures ([[perf-baseline]]). Use it as a
fast correctness check; the perf run is the throughput check.

## Keploy — record → replay (operator-on-demand, privileged)

Config: `keploy/keploy.yml`. Target: a B160 golden-path image (`registry.weyland.lab/golden-python-fastapi`,
port 8080) — self-contained, no external deps, so a full cycle needs only the image. Point the config's
`command` at any other `golden-*` image to capture that one.

**Requires Linux kernel >= 5.10 + eBPF (privileged).** Keploy is installed on the host and run with
sudo; it is never wired into CI or a schedule. Install: https://keploy.io/docs/server/installation/.

```
# one-time: the docker network the config names
docker network create keploy-network

# 1. RECORD — Keploy launches the image (from keploy.yml `command`) and intercepts its inbound calls.
sudo -E keploy record            # reads ./keploy/keploy.yml
#    in a second shell, drive representative traffic while it records:
curl -s localhost:8080/health;  curl -s localhost:8080/ready;  curl -s localhost:8080/hello
#    stop with Ctrl-C -> writes keploy/test-sets/test-set-0/{tests/,mocks.yaml}

# 2. COMMIT the generated corpus:  git add keploy/test-sets/   (these files ARE the regression tests)

# 3. REPLAY as regression — reruns the image, replays every recorded request, diffs the responses:
sudo -E keploy test              # non-zero exit on any diff => a regression
```

A replay diff is a behavioural regression in that service's API. Re-record (and re-commit) deliberately
only when the change is intended — the same way a snapshot test is updated on purpose, never to make red
go green.

## Why both (and why not more)

Bruno covers hand-authored, always-green smoke + any request you want to keep as a committed example.
Keploy covers "capture what the service actually does under real traffic" without hand-writing each case.
Together they are the lab's Git-native API regression surface. Anything heavier (a hosted API platform,
traffic replay at scale) is out of scope for a solo $0 LAN lab — see the survey
([concepts/ai-dev-tooling-survey.md](../concepts/ai-dev-tooling-survey.md)).
