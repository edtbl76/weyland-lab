#!/usr/bin/env python3
"""B103 prompt federation — OUTBOUND sync (Phase 1). Bifrost (SoT) -> Langfuse + MLflow.

Bifrost's Prompt Repository is the single authoring source of truth. This mirrors every prompt's LATEST version OUT to:
  - Langfuse Prompts  = the RUNTIME fetch surface. Apps `get_prompt(name)` from here; because their calls are traced
    (LiteLLM -> Langfuse, B103), fetching links the trace to the prompt VERSION. This is where linkage is created.
  - MLflow Prompt Registry = a catalog mirror (text-flattened), so the two existing prompt registries stay in step.

Idempotent: compares the Bifrost content hash against each downstream's current `production` version and only writes a
new version when it CHANGED (no version churn on re-run). Every propagated version is STAMPED
(`synced-from-bifrost:<hash>`) so the Phase-2 inbound reconciler can skip sync-origin versions and avoid loops.

Format normalizer (the three tools model prompts differently):
  - Bifrost & Langfuse: chat messages `[{role,content}]`, `{{var}}` (mustache, auto-extracted / .compile()).
  - MLflow: plain-string template, `{var}` (str.format). So Bifrost -> MLflow flattens messages + translates {{v}}->{v}.

Langfuse is reached via its PUBLIC REST API with httpx + Basic auth (pk/sk) — NOT the langfuse SDK. The SDK 3.x caps
`packaging<26` which conflicts with the dagster mega-lockfile's pinned `packaging==26.2`; REST keeps this dep-free.

Run (in the dagster-user-code pod, which has httpx + mlflow-skinny + the LANGFUSE_* creds):
    kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/sync_prompts.py
(Phase 2 will add the reverse direction + a Postgres `prompt_federation_manifest`; Phase 1 uses downstream-content
comparison as the state, so no manifest table yet.) See aidlc-docs/prompt-federation-design.md.
"""
import hashlib
import json
import os
import re

import httpx

BIFROST = os.getenv("BIFROST_URL", "http://bifrost.weyland.svc.cluster.local:8080")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://langfuse.weyland.svc:3000")
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000")
STAMP = "synced-from-bifrost"          # provenance prefix — Phase-2 inbound skips versions whose origin is this
MIRROR_MLFLOW = os.getenv("SYNC_MLFLOW", "1") != "0"   # set SYNC_MLFLOW=0 to skip the MLflow catalog mirror

_VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")   # {{var}} -> {var} for the MLflow (str.format) dialect


def _hash(messages):
    """Content identity = hash of the ordered (role, content) pairs. Downstream version numbers drift independently
    across tools, so content — not version — is the reconciliation key."""
    payload = [[m["role"], m["content"]] for m in messages]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _to_mlflow_text(messages):
    """Flatten chat -> string and translate {{var}} -> {var}. Single-message prompts (most system/user prompts) map to
    their bare content so the app prompts match their existing MLflow templates exactly (idempotent skip)."""
    if len(messages) == 1:
        text = messages[0]["content"]
    else:
        text = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in messages)
    return _VAR.sub(r"{\1}", text)


def read_bifrost():
    """Every Bifrost prompt's LATEST version as {name, messages:[{role,content}], commit}."""
    c = httpx.Client(base_url=BIFROST, timeout=30)
    prompts = c.get("/api/prompt-repo/prompts", params={"limit": 1000}).json().get("prompts") or []
    out = []
    for p in prompts:
        versions = c.get(f"/api/prompt-repo/prompts/{p['id']}/versions").json().get("versions") or []
        if not versions:
            continue
        latest = next((v for v in versions if v.get("is_latest")), max(versions, key=lambda v: v["version_number"]))
        msgs = [m["message"] for m in sorted(latest["messages"], key=lambda m: m["order_index"])]
        out.append({"name": p["name"], "messages": msgs, "commit": latest.get("commit_message", "")})
    return out


def sync_langfuse(items):
    """Upsert each Bifrost prompt into Langfuse via the public REST API (httpx + Basic auth pk/sk). GET the current
    production version and compare content hashes — only POST a new version when it CHANGED. The new version is
    stamped via commitMessage/tags for the Phase-2 inbound skip."""
    c = httpx.Client(base_url=LANGFUSE_HOST, timeout=30,
                     auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]))
    upserted = unchanged = 0
    for it in items:
        h = _hash(it["messages"])
        r = c.get(f"/api/public/v2/prompts/{it['name']}", params={"label": "production"})
        if r.status_code == 200:               # exists — skip if production already matches this content
            cur = r.json().get("prompt")
            if isinstance(cur, list):          # chat prompt = list of {role,content}
                cur_msgs = [{"role": m.get("role"), "content": m.get("content")} for m in cur]
                if _hash(cur_msgs) == h:
                    unchanged += 1
                    continue
        body = {"name": it["name"], "type": "chat", "labels": ["production"],
                "prompt": [{"role": m["role"], "content": m["content"]} for m in it["messages"]]}
        resp = c.post("/api/public/v2/prompts", json={**body, "commitMessage": f"{STAMP}:{h}", "tags": [STAMP]})
        if resp.status_code >= 400:            # a build that rejects commitMessage/tags -> retry minimal
            resp = c.post("/api/public/v2/prompts", json=body)
        resp.raise_for_status()
        upserted += 1
    return upserted, unchanged


def sync_mlflow(items):
    import mlflow
    mlflow.set_tracking_uri(MLFLOW_URI)
    try:
        from mlflow.genai import load_prompt, register_prompt, set_prompt_alias
    except Exception:
        from mlflow import load_prompt, register_prompt, set_prompt_alias
    upserted = unchanged = 0
    for it in items:
        text = _to_mlflow_text(it["messages"])
        try:
            cur = load_prompt(f"prompts:/{it['name']}@production")
            if cur.template == text:
                unchanged += 1
                continue
        except Exception:
            pass
        try:
            pv = register_prompt(name=it["name"], template=text, commit_message=STAMP)
        except TypeError:
            pv = register_prompt(name=it["name"], template=text)
        set_prompt_alias(it["name"], "production", pv.version)
        upserted += 1
    return upserted, unchanged


def main():
    items = read_bifrost()
    print(f"Bifrost prompts (latest versions): {len(items)}")
    lu, ln = sync_langfuse(items)
    print(f"Langfuse: {lu} upserted, {ln} unchanged")
    if MIRROR_MLFLOW:
        try:
            mu, mn = sync_mlflow(items)
            print(f"MLflow:   {mu} upserted, {mn} unchanged")
        except Exception as e:                 # mlflow-skinny may lack genai.register_prompt — Langfuse is the payoff
            print(f"MLflow:   SKIPPED (non-fatal): {type(e).__name__}: {e}")
    else:
        print("MLflow:   skipped (SYNC_MLFLOW=0)")


if __name__ == "__main__":
    main()
