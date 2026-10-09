#!/usr/bin/env python3
"""The Bifrost client_config settings the lab owns (B202) — GitOps-durable source of truth.

They live only in `config.db`, so this script restores them after a rebuild. Run:
    kubectl -n weyland exec -i deploy/weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - < scripts/register_bifrost_client_config.py

- `whitelisted_routes` includes `/metrics`. From v2.2.6, with dashboard auth off, every non-public route needs
  `X-Bifrost-Setup-Token`, and `/metrics` is not on Bifrost's built-in public list: Prometheus got 401 and
  `bifrost_cost_total` vanished (BifrostSpendObserved blind). An entry is an exact match, or a trailing `*` prefix.
- `allowed_origins` includes the dashboard's own origin. Empty already means localhost-only; this makes it explicit
  (the v2 setup checklist's "Restrict CORS origins").
- `enforce_auth_on_inference` is true: every inference call must carry a virtual key (dashboard credentials do not
  count). All callers already do (LiteLLM `realm-llm`, the coding agents' `x-bf-vk`, the Realm), checked 2026-10-09.

PUT /api/config copies many client_config fields unconditionally (booleans included), so a partial body would reset
them. This reads the FULL client_config, changes only the owned fields, sends nothing else (framework_config and
auth_config are left alone when absent), then reads it back. Idempotent: no write when everything is already set.
Runbook: docs/runbooks/mcp-gateway.md § Bifrost setup token.
"""
import os

BASE_ENV = "BIFROST_URL"   # required, passed by the runbook command; no default, so a missing URL fails loudly
LIST_FIELDS = {"whitelisted_routes": ["/metrics"], "allowed_origins": ["https://bifrost.weyland.lab"]}
FLAG_FIELDS = {"enforce_auth_on_inference": True}


def _read(client) -> dict:
    resp = client.get("/api/config")
    if resp.status_code != 200:
        raise SystemExit(f"GET /api/config {resp.status_code} (is BIFROST_SETUP_TOKEN set?): {resp.text[:200]}")
    return resp.json().get("client_config") or {}


def _desired(cc: dict) -> dict:
    out = dict(cc)
    for field, wanted in LIST_FIELDS.items():
        current = list(cc.get(field) or [])
        out[field] = current + [v for v in wanted if v not in current]
    out.update(FLAG_FIELDS)
    return out


def _settled(cc: dict) -> bool:
    return (all(v in (cc.get(f) or []) for f, wanted in LIST_FIELDS.items() for v in wanted)
            and all(cc.get(f) is v for f, v in FLAG_FIELDS.items()))


def ensure_settings(client) -> str:
    cc = _read(client)
    if _settled(cc):
        return "unchanged: client_config already as owned"
    resp = client.put("/api/config", json={"client_config": _desired(cc)})
    if resp.status_code >= 300:
        raise SystemExit(f"PUT /api/config {resp.status_code}: {resp.text[:300]}")
    stored = _read(client)
    if not _settled(stored):
        got = {f: stored.get(f) for f in (*LIST_FIELDS, *FLAG_FIELDS)}
        raise SystemExit(f"read-back: stored {got}, expected {LIST_FIELDS} and {FLAG_FIELDS}")
    return "updated: " + ", ".join(f"{f} = {stored.get(f)}" for f in (*LIST_FIELDS, *FLAG_FIELDS))


def main():
    base = os.getenv(BASE_ENV) or ""
    if not base:
        raise SystemExit(f"{BASE_ENV} is not set (see the run command in this script's docstring)")
    import httpx

    headers = {"X-Bifrost-Setup-Token": os.environ["BIFROST_SETUP_TOKEN"]} if os.getenv("BIFROST_SETUP_TOKEN") else {}  # B202: v2.2.6+ setup lock (auth off)
    with httpx.Client(base_url=base, timeout=30, headers=headers) as client:
        print(ensure_settings(client))


if __name__ == "__main__":
    main()
