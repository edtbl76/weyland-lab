#!/usr/bin/env python3
"""Idempotent Bifrost governance registration (B111) — a global budget ceiling + per-consumer virtual keys with caps.

Run against the in-cluster Bifrost admin API (no auth in-cluster):
    kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_governance.py

MODEL: Bifrost budgets are consumer-scoped (team / virtual-key), NOT per-provider. So:
  - a **team** ("weyland") carries the GLOBAL master ceiling ($20/mo) — total Bifrost spend can't exceed it,
  - each **virtual key** (a consumer lane) carries a sub-cap; VKs belong to the team.
Self-hosted providers (Ollama/vLLM/SGLang) cost $0 → they consume $0 of any budget automatically (no exemption needed).
Everything hosted (incl. HF/Groq/OpenRouter) counts. NOTE: HF also burns HF-side credits Bifrost may not meter — watch it.

Idempotent: existing team/VKs are UPDATED (budget), missing ones CREATED. Reset period = monthly (1M).
VK values are SECRETS printed ONCE on create — capture them into SealedSecrets, do NOT commit them.
"""
import os, json, httpx

BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")
RESET = "1M"

TEAM = {"name": "weyland", "budget": {"max_limit": 20.0, "reset_duration": RESET}}   # GLOBAL master ceiling
VKS = [
    {"name": "coding-agents", "description": "B15 coding agents (Cline/Cursor/Claude Code) via Bifrost",
     "budget": {"max_limit": 10.0, "reset_duration": RESET}},
    {"name": "operator",      "description": "B66 operator brain (Haiku)",
     "budget": {"max_limit": 10.0, "reset_duration": RESET}},
    {"name": "chat-eval",     "description": "RAG / eval / smoke traffic",
     "budget": {"max_limit": 5.0,  "reset_duration": RESET}},
]

c = httpx.Client(base_url=BASE, timeout=30)

def _id(obj):   # tolerate {id} or {team:{id}} / {virtual_key:{id}} response shapes
    return obj.get("id") or (obj.get("team") or obj.get("virtual_key") or {}).get("id")

def upsert_team(t):
    teams = c.get("/api/governance/teams").json().get("teams") or []
    hit = next((x for x in teams if x.get("name") == t["name"]), None)
    if hit:
        tid = hit["id"]
        r = c.put(f"/api/governance/teams/{tid}", json={"budget": t["budget"]})
        print(f"team {t['name']:14} UPDATED  id={tid}  cap ${t['budget']['max_limit']:.2f}/{RESET}  ({r.status_code})")
        return tid
    r = c.post("/api/governance/teams", json=t); r.raise_for_status()
    tid = _id(r.json())
    print(f"team {t['name']:14} CREATED  id={tid}  cap ${t['budget']['max_limit']:.2f}/{RESET}")
    return tid

def upsert_vk(vk, team_id):
    vks = c.get("/api/governance/virtual-keys").json().get("virtual_keys") or []
    hit = next((x for x in vks if x.get("name") == vk["name"]), None)
    if hit:
        vid = hit["id"]
        r = c.put(f"/api/governance/virtual-keys/{vid}", json={"budget": vk["budget"], "is_active": True})
        print(f"  vk {vk['name']:16} UPDATED  cap ${vk['budget']['max_limit']:.2f}/{RESET}  [value unchanged]  ({r.status_code})")
        return
    body = {**vk, "team_id": team_id, "is_active": True}
    r = c.post("/api/governance/virtual-keys", json=body); r.raise_for_status()
    j = r.json()
    val = j.get("value") or (j.get("virtual_key") or {}).get("value") or "(see response — capture the vk value)"
    print(f"  vk {vk['name']:16} CREATED  cap ${vk['budget']['max_limit']:.2f}/{RESET}")
    print(f"     VALUE={val}   <-- SECRET: seal this, do NOT commit")

if __name__ == "__main__":
    tid = upsert_team(TEAM)
    for vk in VKS:
        upsert_vk(vk, tid)
    print("\ndone — verify: GET /api/governance/{teams,virtual-keys,budgets}. Seal the printed VK value(s).")
