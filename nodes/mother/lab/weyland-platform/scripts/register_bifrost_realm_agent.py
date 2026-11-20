#!/usr/bin/env python3
"""The Realm of Agents behind Bifrost's Agent Gateway (B249, 2026-11-19) — GitOps-durable source of truth.

The registration lives only in Bifrost's `config.db`, so this script is its recorded definition (and restores it after a
rebuild). Run in-cluster, like the other register scripts (mode as the argument):
    kubectl -n weyland exec -i deploy/weyland-guard -c weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - <mode> < scripts/register_bifrost_realm_agent.py

Modes:
  ensure-vk  the operator's virtual key `realm-operator` exists (created if absent). Prints ONLY one line,
             `REALM_GATEWAY_VK=<value>`, meant to be appended to scripts/.env and sealed (seal_realm_gateway.sh); never
             run it without redirecting the output. Bifrost generates the value (a supplied one is ignored) and returns
             it on read under the setup token.
  register   the agent `realm` is as owned: the Realm's in-cluster card; granted to `realm-operator` ONLY
             (allow_by_default off); the caller's key NOT forwarded (the Realm's agents use their own key for tools);
             Bifrost sends `X-Realm-Gateway-Token` from its env (`env.REALM_GATEWAY_TOKEN`) on every call it forwards.
             Needs the gateway settings first (register_bifrost_client_config.py) and the Realm's v1 card live.
  check      read-only: the same facts; exit 1 naming any drift.

Why "granted to realm-operator only" matters: the Realm honours `allow_paid` only when the gateway token arrives, and
Bifrost adds it to every forwarded call, so every granted key can spend on the paid lane. Grant another caller only
after deciding that (and say so here). Runbook: docs/runbooks/realm-of-agents.md § Through Bifrost's Agent Gateway.
"""
import os
import sys

AGENT = "realm"
VK_NAME = "realm-operator"
CARD_URL = "http://realm-of-agents.weyland.svc.cluster.local:8080/.well-known/agent-card.json"
TOKEN_HEADER = "X-Realm-Gateway-Token"
TOKEN_REF = "env.REALM_GATEWAY_TOKEN"
BASE_ENV = "BIFROST_URL"   # required, passed by the run command; no default, so a missing URL fails loudly


def _ok(resp, what):
    if resp.status_code >= 300:
        raise SystemExit(f"{what} {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _find_vk(client):
    body = _ok(client.get("/api/governance/virtual-keys"), "GET /api/governance/virtual-keys")
    return next((v for v in body.get("virtual_keys") or [] if v.get("name") == VK_NAME), None)


def ensure_vk(client) -> None:
    vk = _find_vk(client)
    if vk is None:
        created = _ok(client.post("/api/governance/virtual-keys",
                                  json={"name": VK_NAME, "description": "the weyland-operator calling the Realm "
                                                                        "through the Agent Gateway (B249)"}),
                      "POST /api/governance/virtual-keys")
        vk = created.get("virtual_key") or created
    value = vk.get("value") or ""
    if not value or "*" in value or "REDACT" in value.upper():
        raise SystemExit(f"the {VK_NAME} key's value is not readable (got a masked or empty value); nothing printed")
    print(f"REALM_GATEWAY_VK={value}")


def _owned(vk_id: str) -> dict:
    return {"name": AGENT, "agent_card_url": CARD_URL, "enabled": True, "allow_by_default": False,
            "forward_accepted_credential": False, "virtual_key_ids": [vk_id],
            "runtime_auth": {"type": "headers", "headers": {TOKEN_HEADER: TOKEN_REF}}}


def _token_ref(agent: dict):
    """The env reference behind the gateway-token header, as Bifrost reads it back (the value itself is redacted)."""
    ra = agent.get("runtime_auth") or {}
    stored = (ra.get("headers") or {}).get(TOKEN_HEADER)
    if ra.get("type") != "headers" or stored is None:
        return None
    return stored.get("ref") if isinstance(stored, dict) else stored


def _drift(agent: dict, vk_id: str) -> list:
    out = []
    if agent.get("agent_card_url") != CARD_URL:
        out.append(f"card URL is {agent.get('agent_card_url')!r}, not {CARD_URL!r}")
    if agent.get("enabled") is not True:
        out.append("not enabled")
    if agent.get("allow_by_default") is not False or (agent.get("virtual_key_ids") or []) != [vk_id]:
        out.append(f"granted to {agent.get('virtual_key_ids')} (allow_by_default {agent.get('allow_by_default')}), "
                   f"not {VK_NAME} only: every granted key can spend on the Realm's paid lane")
    if agent.get("forward_accepted_credential") is not False:
        out.append("forwards the caller's key to the Realm")
    if _token_ref(agent) != TOKEN_REF:
        out.append(f"the gateway token header is not {TOKEN_REF}: the Realm would see no token and stay free-only")
    return out


def _get_agent(client):
    resp = client.get(f"/api/agents/{AGENT}")
    if resp.status_code == 404:
        return None
    return _ok(resp, f"GET /api/agents/{AGENT}")


def register(client) -> str:
    vk = _find_vk(client)
    if vk is None:
        raise SystemExit(f"no {VK_NAME} virtual key: run the ensure-vk mode first (and seal its value)")
    agent = _get_agent(client)
    if agent is None:
        _ok(client.post("/api/agents", json=_owned(vk["id"])), "POST /api/agents")
        verb = "registered"
    elif _drift(agent, vk["id"]):
        _ok(client.put(f"/api/agents/{AGENT}", json=_owned(vk["id"])), f"PUT /api/agents/{AGENT}")
        verb = "updated"
    else:
        return f"unchanged: {AGENT} registered as owned"
    left = _drift(_get_agent(client) or {}, vk["id"])
    if left:
        raise SystemExit("read-back: " + "; ".join(left))
    return f"{verb}: {AGENT} → {CARD_URL}, granted to {VK_NAME} only, gateway token from {TOKEN_REF}"


def check(client) -> int:
    vk = _find_vk(client)
    agent = _get_agent(client)
    problems = []
    if vk is None:
        problems.append(f"no {VK_NAME} virtual key")
    if agent is None:
        problems.append(f"{AGENT} is not registered")
    if vk is not None and agent is not None:
        problems += _drift(agent, vk["id"])
    if problems:
        print("DRIFT: " + "; ".join(problems))
        return 1
    print(f"OK: {AGENT} → {CARD_URL}, granted to {VK_NAME} only, gateway token from {TOKEN_REF}")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    modes = {"ensure-vk", "register", "check"}
    if len(argv) != 1 or argv[0] not in modes:
        raise SystemExit(f"usage: python - {{{'|'.join(sorted(modes))}}} < register_bifrost_realm_agent.py")
    base = os.getenv(BASE_ENV) or ""
    if not base:
        raise SystemExit(f"{BASE_ENV} is not set (see the run command in this script's docstring)")
    import httpx

    headers = {"X-Bifrost-Setup-Token": os.environ["BIFROST_SETUP_TOKEN"]} if os.getenv("BIFROST_SETUP_TOKEN") else {}
    with httpx.Client(base_url=base, timeout=60, headers=headers) as client:
        if argv[0] == "ensure-vk":
            ensure_vk(client)
            return 0
        if argv[0] == "register":
            print(register(client))
            return 0
        return check(client)


if __name__ == "__main__":
    sys.exit(main())
