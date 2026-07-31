#!/usr/bin/env python3
"""Idempotent Bifrost governance registration (B111) — per-PROVIDER monthly budget caps.

Run against the in-cluster Bifrost admin API (no auth in-cluster):
    kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_governance.py

v1.6.7 MODEL (reverse-engineered from the UI): budgets live on a **model-config** = (provider, model_name, scope),
created via `POST /api/governance/model-configs` with nested budgets. This is PER-PROVIDER (not per-VK — in v1.6.7 VKs
carry identity + tool-scoping, NOT budgets). `model_name:"*"` = All Models, `scope:"global"` = all traffic for that
provider. Budgets only bite on $-billing providers; free/self-hosted cost $0 (and HF burns HF-side credits Bifrost
doesn't meter), so they're intentionally left uncapped.

Idempotent: a matching (provider, *, global) model-config is left as-is (adjust amounts in the UI or bump the digit here
and delete+recreate). Reset = monthly (1M). model-configs are NOT secrets, so this is safe to run + commit.

NOTE: the 3 consumer VKs (coding-agents / operator / chat-eval) are a SEPARATE concern (identity/auth for the coding-agent
edge, tool-scoping) — created out-of-band; their values are SealedSecrets. They are not budgets and not managed here.
"""
import os, httpx

BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")

# provider -> monthly USD cap. Anthropic higher (operator brain, funded $20); everything else paid = $10.
CAPS = {
    "anthropic": 20,
    "openai": 10, "gemini": 10, "deepseek": 10, "cohere": 10, "mistral": 10,
    "openrouter": 10, "perplexity": 10, "fireworks": 10, "xai": 10, "opencode-zen": 10,
    "cerebras": 10, "parasail": 10, "replicate": 10, "runway": 10, "runware": 10,
    "wafer": 10, "elevenlabs": 10,
}
# UNCAPPED (cost $0 / not $-metered by Bifrost): ollama, vllm, sgl, huggingface, groq

c = httpx.Client(base_url=BASE, timeout=30)

def upsert(provider, cap):
    mcs = c.get("/api/governance/model-configs?limit=500").json().get("model_configs") or []
    hit = next((m for m in mcs if m.get("provider") == provider
                and m.get("model_name") == "*" and m.get("scope") == "global"), None)
    if hit:
        cur = (hit.get("budgets") or [{}])[0].get("max_limit")
        print(f"{provider:14} EXISTS   cap ${cur}/1M   (target ${cap} — left as-is)")
        return
    body = {"provider": provider, "model_name": "*", "scope": "global",
            "budgets": [{"max_limit": cap, "reset_duration": "1M"}]}
    r = c.post("/api/governance/model-configs", json=body)
    ok = r.status_code < 300
    print(f"{provider:14} {'CREATED ' if ok else 'FAILED  '} cap ${cap}/1M   ({r.status_code}){'' if ok else ' '+r.text[:120]}")

if __name__ == "__main__":
    print("Bifrost per-provider monthly budget caps (model_name=*, scope=global):\n")
    for prov, cap in CAPS.items():
        upsert(prov, cap)
    print("\ndone — verify in UI (Budgets & Limits) or GET /api/governance/model-configs.")
