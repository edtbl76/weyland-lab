#!/usr/bin/env python3
"""Keep Bifrost's /metrics public under the v2.2.6 setup lock (B202) — GitOps-durable source of truth.

From v2.2.6, with dashboard auth off, every non-public route needs `X-Bifrost-Setup-Token`, and `/metrics` is NOT on
Bifrost's built-in public list: Prometheus got 401, `up{job="bifrost"}` went to 0 and `bifrost_cost_total` vanished
(BifrostSpendObserved blind). The operator setting `client_config.whitelisted_routes` exempts a route (exact match,
or a trailing `*` for a prefix); it lives only in `config.db`, so this script restores it after a rebuild. Run:
    kubectl -n weyland exec -i deploy/weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - < scripts/register_bifrost_client_config.py

PUT /api/config copies many client_config fields unconditionally (booleans included), so a partial body would reset
them. This reads the FULL client_config, changes only `whitelisted_routes`, sends nothing else (framework_config and
auth_config are left alone when absent), then reads it back. Idempotent: no write when the route is already there.
Runbook: docs/runbooks/mcp-gateway.md § Bifrost setup token.
"""
import os

BASE_ENV = "BIFROST_URL"   # required, passed by the runbook command; no default, so a missing URL fails loudly
ROUTES = ["/metrics"]


def _routes(config: dict) -> list:
    return list((config.get("client_config") or {}).get("whitelisted_routes") or [])


def _read(client) -> dict:
    resp = client.get("/api/config")
    if resp.status_code != 200:
        raise SystemExit(f"GET /api/config {resp.status_code} (is BIFROST_SETUP_TOKEN set?): {resp.text[:200]}")
    return resp.json()


def ensure_routes(client) -> str:
    config = _read(client)
    current = _routes(config)
    missing = [r for r in ROUTES if r not in current]
    if not missing:
        return f"unchanged: {', '.join(ROUTES)} already whitelisted"
    body = {"client_config": {**config["client_config"], "whitelisted_routes": current + missing}}
    resp = client.put("/api/config", json=body)
    if resp.status_code >= 300:
        raise SystemExit(f"PUT /api/config {resp.status_code}: {resp.text[:300]}")
    stored = _routes(_read(client))
    if any(r not in stored for r in ROUTES):
        raise SystemExit(f"read-back: whitelisted_routes = {stored}, expected to include {ROUTES}")
    return f"updated: whitelisted_routes = {stored}"


def main():
    base = os.getenv(BASE_ENV) or ""
    if not base:
        raise SystemExit(f"{BASE_ENV} is not set (see the run command in this script's docstring)")
    import httpx

    headers = {"X-Bifrost-Setup-Token": os.environ["BIFROST_SETUP_TOKEN"]} if os.getenv("BIFROST_SETUP_TOKEN") else {}  # B202: v2.2.6+ setup lock (auth off)
    with httpx.Client(base_url=base, timeout=30, headers=headers) as client:
        print(ensure_routes(client))


if __name__ == "__main__":
    main()
