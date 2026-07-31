#!/usr/bin/env python3
"""Idempotent Bifrost routing rules (B111) — use-case aliases → primary provider/model.

Clients request a **use-case alias** as the model (`wl-coding`, `wl-rag`, …); a CEL rule `model == "wl-X"` routes it to
the primary target. Run:
    kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_routing.py

MECHANISM (v1.6.7): `POST /api/governance/routing-rules` {name, cel_expression, targets:[{provider,model,weight}], scope,
priority, chain_rule}. Targets are **WEIGHTED (probabilistic), NOT ordered fallback** — so each rule sets the PRIMARY.
**VERIFIED 2026-07-31: `chain_rule` is NOT on-failure fallback** — a rule → down provider (502 connection refused, the
documented trigger) with chain_rule:true + a 2nd same-CEL rung did NOT cascade. Availability failover therefore CANNOT be
a routing rule — it needs request-level `fallbacks:[...]` (client sends) or VK-level `provider_configs` (server-side,
coarse). Cost-degrade `budget_used > 90 → free` IS a normal routing rule (CEL var confirmed) — buildable when wanted.

Primary choices: tool-heavy use cases lead a **tool-capable** provider (coding→kimi, agentic→haiku); tool-free general lead
**free** (groq always-on, or ollama-local where private/appropriate). NOTE: the ollama-local primaries (rag/reason/judge)
require rogueone awake — until fallbacks land, those aliases fail when the GPU box sleeps.
"""
import os, httpx

BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")

# alias -> (provider, model). Retarget freely — one edit each.
RULES = [
    ("wl-default", "groq",         "openai/gpt-oss-120b"),   # free hosted general
    ("wl-speed",   "groq",         "openai/gpt-oss-120b"),   # free hosted, fast
    ("wl-coding",  "opencode-zen", "kimi-k3"),               # coding specialist + tool-capable
    ("wl-agentic", "anthropic",    "claude-haiku-4-5"),      # reliable cheap tool-calling
    ("wl-rag",     "ollama",       "gpt-oss:20b"),           # free local (private)
    ("wl-reason",  "ollama",       "qwen3:30b-a3b"),         # free local reasoning model
    ("wl-judge",   "ollama",       "qwen2.5:7b"),            # free local judge (the current one)
    ("wl-search",  "perplexity",   "sonar"),                 # ONLY web-search provider
    ("wl-big-oss", "openrouter",   "minimax/minimax-m3"),    # big frontier OSS via aggregator
]

c = httpx.Client(base_url=BASE, timeout=30)
existing = {r.get("name") for r in (c.get("/api/governance/routing-rules?limit=500").json().get("rules") or [])}
for i, (alias, prov, model) in enumerate(RULES):
    if alias in existing:
        print(f"{alias:12} EXISTS  -> {prov}/{model}"); continue
    body = {"name": alias, "cel_expression": f'model == "{alias}"',
            "targets": [{"provider": prov, "model": model, "weight": 1}],
            "scope": "global", "priority": 10 + i}
    r = c.post("/api/governance/routing-rules", json=body)
    ok = r.status_code < 300
    print(f"{alias:12} {'CREATED' if ok else 'FAILED '} -> {prov}/{model}  ({r.status_code}){'' if ok else ' '+r.text[:100]}")
print("\ndone — clients request the alias as `model` (e.g. wl-coding). Fallbacks + budget-overflow = next iteration.")
