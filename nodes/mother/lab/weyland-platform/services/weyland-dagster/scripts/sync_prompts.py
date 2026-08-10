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
RECONCILE_INBOUND = os.getenv("SYNC_INBOUND", "1") != "0"   # Phase 2 — set SYNC_INBOUND=0 for outbound-only (no pull-back)
_VAR_TO_BF = re.compile(r"\{(\w+)\}")   # MLflow {var} -> Bifrost {{var}} (MLflow templates never use {{}})

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


# ==================== Phase 2 — INBOUND reconcile (native Langfuse/MLflow edits -> Bifrost) ====================

def _to_bifrost_from_mlflow(template, name):
    """Reverse-normalize an MLflow string template -> Bifrost chat messages: wrap in a single message (role heuristic),
    translate {var} -> {{var}}."""
    role = "system" if name.endswith("_system") else "user"
    return [{"role": role, "content": _VAR_TO_BF.sub(r"{{\1}}", template)}]


def _epoch(v):
    """Best-effort epoch seconds from a Langfuse ISO string or an MLflow epoch-ms number — for last-write-wins."""
    try:
        if isinstance(v, (int, float)):
            return float(v) / 1000.0
        from datetime import datetime
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _bifrost_ids():
    c = httpx.Client(base_url=BIFROST, timeout=30)
    return {p["name"]: p["id"] for p in (c.get("/api/prompt-repo/prompts", params={"limit": 1000}).json().get("prompts") or [])}


def _langfuse_native(c_lf, name):
    """Latest Langfuse production version IF natively authored (NOT synced-from-bifrost). Returns (messages, epoch)."""
    r = c_lf.get(f"/api/public/v2/prompts/{name}", params={"label": "production"})
    if r.status_code != 200:
        return None
    v = r.json()
    if STAMP in (v.get("tags") or []) or str(v.get("commitMessage") or "").startswith(STAMP):
        return None                                # sync-origin, not a human edit
    prompt = v.get("prompt")
    if not isinstance(prompt, list):
        return None
    msgs = [{"role": m.get("role"), "content": m.get("content")} for m in prompt]
    return (msgs, _epoch(v.get("updatedAt") or v.get("createdAt")))


def _mlflow_native(name):
    try:
        from mlflow.genai import load_prompt
    except Exception:
        from mlflow import load_prompt
    try:
        pv = load_prompt(f"prompts:/{name}@production")
    except Exception:
        return None
    if str(getattr(pv, "commit_message", "") or "").startswith(STAMP):
        return None
    return (_to_bifrost_from_mlflow(pv.template, name), _epoch(getattr(pv, "creation_timestamp", 0)))


def reconcile_inbound(bifrost_items):
    """Pull native (human-authored) Langfuse/MLflow edits back into Bifrost (the SoT). LOOP-SAFE: only pulls when the
    downstream content-hash DIFFERS from Bifrost's canonical, so once pulled (Bifrost matches) the next run skips —
    regardless of stamping. Conflict (edited natively in BOTH stores) = last-write-wins by version timestamp + a WARNING."""
    canon = {it["name"]: _hash(it["messages"]) for it in bifrost_items}
    ids = _bifrost_ids()
    c_bf = httpx.Client(base_url=BIFROST, timeout=30)
    c_lf = httpx.Client(base_url=LANGFUSE_HOST, timeout=30,
                        auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]))
    pulled = 0
    for name, h in canon.items():
        cands = []                                 # (epoch, source, messages)
        lf = _langfuse_native(c_lf, name)
        if lf and _hash(lf[0]) != h:
            cands.append((lf[1], "langfuse", lf[0]))
        if MIRROR_MLFLOW:
            try:
                mf = _mlflow_native(name)
                if mf and _hash(mf[0]) != h:
                    cands.append((mf[1], "mlflow", mf[0]))
            except Exception:
                pass
        if not cands:
            continue
        if len(cands) > 1:
            print(f"  CONFLICT {name}: native edits in {[c[1] for c in cands]} -> last-write-wins by timestamp")
        _, source, msgs = max(cands, key=lambda c: c[0])
        pid = ids.get(name)
        if not pid:
            print(f"  skip {name}: native in {source} but not in Bifrost (create it in Bifrost first)")
            continue
        c_bf.post(f"/api/prompt-repo/prompts/{pid}/versions", json={
            "commit_message": f"reconciled-from-{source}:{_hash(msgs)}",
            "messages": [{"role": m["role"], "content": m["content"]} for m in msgs]})
        pulled += 1
        print(f"  pulled {name} <- {source}")
    return pulled


def main():
    if RECONCILE_INBOUND:                          # Phase 2 — pull native downstream edits back to Bifrost FIRST,
        n = reconcile_inbound(read_bifrost())      # so the outbound pass below re-propagates them (stamped).
        print(f"Inbound: {n} native edit(s) pulled into Bifrost" if n else "Inbound: 0 native edits")
    items = read_bifrost()                          # re-read (post-inbound) — Bifrost is canonical
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
