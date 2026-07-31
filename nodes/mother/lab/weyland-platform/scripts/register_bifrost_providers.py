#!/usr/bin/env python3
"""Point each Bifrost provider's key at an env-var reference (env.VAR) so keys resolve from the SealedSecret'd pod env
at runtime — no plaintext keys in the PVC (B111 key-sealing). Idempotent.

ORDER MATTERS: apply the `bifrost-provider-keys` SealedSecret + add `envFrom` to the Bifrost pod + RESTART Bifrost FIRST.
If you flip a provider to `env.VAR` before that var exists in the pod env, that provider's key resolves EMPTY and breaks.

Two passes (safe):
  1) add env-ref keys (non-destructive — leaves the working plaintext keys in place):
     kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_providers.py
     ... then verify providers still smoke-test OK ...
  2) purge the old plaintext keys (only after step 1 is verified):
     kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_providers.py --purge

Self-hosted (ollama/vllm/sgl) use dummy keys → not in the map, untouched.
"""
import os, sys, httpx

BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")
PURGE = "--purge" in sys.argv

MAP = {  # bifrost provider -> env var (must be present as env on the Bifrost pod via the SealedSecret)
    "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY",
    "cohere": "COHERE_API_KEY", "mistral": "MISTRAL_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY", "perplexity": "PERPLEXITY_API_KEY", "fireworks": "FIREWORKS_API_KEY",
    "xai": "XAI_API_KEY", "cerebras": "CEREBRAS_API_KEY", "groq": "GROQ_API_KEY",
    "huggingface": "HUGGING_FACE_API_KEY", "opencode-zen": "OPENCODE_ZEN_API_KEY",
    "replicate": "REPLICATE_API_KEY", "runway": "RUNWAY_API_KEY", "runware": "RUNWARE_API_KEY",
    "elevenlabs": "ELEVEN_LABS_API_KEY", "together-api-key": "TOGETHER_API_KEY",
}

c = httpx.Client(base_url=BASE, timeout=30)
print(f"mode = {'PURGE plaintext' if PURGE else 'ADD env-refs (non-destructive)'}\n")

for prov, var in MAP.items():
    ref = f"env.{var}"
    r = c.get(f"/api/providers/{prov}/keys")
    if r.status_code != 200:
        print(f"{prov:16} SKIP (no provider / {r.status_code})"); continue
    keys = r.json().get("keys") or []
    # Bifrost stores an env-backed key as type="env" (value read-back is the resolved key, redacted — NOT the literal
    # "env.VAR" string). Detect by type + our "-env" name so re-runs are idempotent (no duplicate-name 409s).
    has_env = any((k.get("value") or {}).get("type") == "env" and k.get("name") == f"{prov}-env" for k in keys)
    if not has_env:
        body = {"name": f"{prov}-env", "value": ref, "models": ["*"], "weight": 1.0}
        a = c.post(f"/api/providers/{prov}/keys", json=body)
        ok = a.status_code < 300
        print(f"{prov:16} {'+env.'+var if ok else 'ADD FAILED'}  ({a.status_code}){'' if ok else ' '+a.text[:100]}")
    else:
        print(f"{prov:16} env.{var} present")
    if PURGE:
        for k in keys:
            if (k.get("value") or {}).get("type") == "plain_text":
                d = c.delete(f"/api/providers/{prov}/keys/{k['id']}")
                print(f"{prov:16}   purged plaintext key ({d.status_code})")

print("\ndone." + ("" if PURGE else "  Verify providers, then re-run with --purge to drop plaintext keys."))
