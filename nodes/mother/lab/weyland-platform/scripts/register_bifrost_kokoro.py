#!/usr/bin/env python3
"""Register the self-hosted Kokoro TTS as a Bifrost custom provider (B111 media lane) — GitOps-durable source of truth.

Bifrost's config lives only in `config.db` (SQLite in the PVC); there is no bootstrap config.json on disk, so a
UI-added provider is LOST on a PVC/config wipe. This script recreates it idempotently — the same pattern as the other
`register_bifrost_*` scripts. Run:
    kubectl -n weyland exec -i deploy/weyland-guard -- python - < scripts/register_bifrost_kokoro.py

Kokoro-FastAPI is OpenAI-compatible (`/v1/audio/speech`), reached at the in-cluster Service. `base_provider_type=openai`;
`allow_private_network=true` because the ClusterIP is private and Bifrost's SSRF guard blocks it otherwise (same as
Ollama). Keyless service → a dummy key (the working UI-added config kept `is_key_less=false`, so we match it).

NOTE (VK durability): the Realm/coding VK must ALSO allow the `kokoro` provider or LiteLLM egress 500s
("Provider 'kokoro' is not allowed for this virtual key"). Capture that allow-list in register_bifrost_governance.py.
Idempotent: skips if the provider already exists (matched by name); the create-path is exercised only on a fresh Bifrost.
"""
import os

import httpx

BASE = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")
PROVIDER = "kokoro"
KOKORO_URL = os.getenv("KOKORO_URL", "http://kokoro.weyland.svc.cluster.local:8880")

PROVIDER_CONFIG = {
    "name": PROVIDER,
    "network_config": {
        "base_url": KOKORO_URL,
        "allow_private_network": True,
        "default_request_timeout_in_seconds": 300,
        "max_retries": 0,
    },
    "custom_provider_config": {
        "base_provider_type": "openai",
        "is_key_less": False,
    },
}
DUMMY_KEY = {"name": f"{PROVIDER}-dummy", "value": "not-needed", "models": ["*"], "weight": 1.0}


def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    if c.get(f"/api/providers/{PROVIDER}").status_code == 200:
        print(f"provider {PROVIDER} already exists — skipping (idempotent)")
        return
    r = c.post("/api/providers", json=PROVIDER_CONFIG)
    if r.status_code >= 300:
        print(f"provider {PROVIDER} FAILED {r.status_code}: {r.text[:300]}")
        return
    print(f"provider {PROVIDER} CREATED")
    k = c.post(f"/api/providers/{PROVIDER}/keys", json=DUMMY_KEY)
    print(f"key {'added' if k.status_code < 300 else 'FAILED ' + str(k.status_code) + ' ' + k.text[:200]}")


if __name__ == "__main__":
    main()
