# Bruno collection — weyland lab APIs (B104)

[Bruno](https://usebruno.com) is a $0, OSS, offline API client whose collections are **plain files
committed to git** (`.bru`) — no cloud account, no LAN-hostile sync. It complements the machine-readable
API-lifecycle catalog (`apis.yaml`, B155): that governs owner/version/status; this is the *executable*
client + a runnable smoke of the request-serving plane.

## Layout

```
bruno/weyland/
  bruno.json                     # collection manifest
  environments/lan.bru           # base URLs (ts, gw) + gw_key secret var
  tool-server/  health · ready · metrics
  gateway/      readiness · liveliness
  authenticated/ gateway-models  # bearer example (needs gw_key; excluded from the keyless run)
```

Base URLs point at the LAN NodePorts from [../../docs/api.md](../../docs/api.md): tool-server
`192.168.1.243:30080`, LiteLLM gateway `192.168.1.243:30400`.

## Run it

Open `bruno/weyland` in the Bruno app, or headless via the CLI (`bru`):

```
cd bruno/weyland
npx --yes @usebruno/cli run tool-server gateway --env lan     # keyless smoke — all green
npx --yes @usebruno/cli run authenticated --env lan --env-var gw_key=$LITELLM_MASTER_KEY
```

The keyless run asserts health/ready/metrics on the two request-serving services (5 requests, 10
assertions) — a fast "is the serving plane answering correctly" check that pairs with the perf baseline
([[perf-baseline]], which measures throughput on the same endpoints).

## Add a request

Drop a `.bru` file in the relevant folder (see `tool-server/health.bru` for the shape: `meta` / `get` /
`assert`). Assert on `res.status` and on JSON fields (`res.body.<field>`); for text bodies assert
`res.body: contains <token>`. Anything needing a bearer goes under `authenticated/` and reads a secret
var so it stays out of the keyless run. Keep base URLs in `environments/lan.bru`, never inline.
